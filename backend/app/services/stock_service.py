import time
import math
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import pytz
from backend.app.utils.helpers import round_num
from backend.app.services.instrument_mapping_service import InstrumentMappingService, NSE_INSTRUMENTS_MASTER
from backend.app.services.upstox_service import UpstoxService

IST = pytz.timezone('Asia/Kolkata')

# In-memory cache for market quotes & candles to reduce latency and rate limits
_QUOTE_CACHE = {}
_HISTORY_CACHE = {}
_INDICES_CACHE = {'data': None, 'timestamp': 0}
CACHE_TTL = 180  # 3 minutes


class StockService:
    """Service for querying Indian stock market data, quotes, historical candles, and indices."""

    @staticmethod
    def search_stocks(query: str, limit: int = 10):
        """
        Searches Indian stocks by symbol or company name using InstrumentMappingService.
        """
        return InstrumentMappingService.search_instruments(query, limit=limit)

    @staticmethod
    def get_market_indices():
        """
        Fetches live data for top Indian benchmark indices:
        - NIFTY 50 (^NSEI)
        - SENSEX (^BSESN)
        - NIFTY BANK (^NSEBANK)
        - NIFTY IT (^CNXIT)
        """
        global _INDICES_CACHE
        now = time.time()
        
        if _INDICES_CACHE['data'] and (now - _INDICES_CACHE['timestamp'] < CACHE_TTL):
            return _INDICES_CACHE['data']

        indices_map = [
            {"symbol": "^NSEI", "name": "NIFTY 50", "exchange": "NSE"},
            {"symbol": "^BSESN", "name": "BSE SENSEX", "exchange": "BSE"},
            {"symbol": "^NSEBANK", "name": "NIFTY BANK", "exchange": "NSE"},
            {"symbol": "^CNXIT", "name": "NIFTY IT", "exchange": "NSE"}
        ]
        
        results = []
        for item in indices_map:
            data = StockService.get_stock_quote(item['symbol'], is_index=True)
            if data and data.get('current_price'):
                results.append({
                    "symbol": item['symbol'],
                    "name": item['name'],
                    "exchange": item['exchange'],
                    "price": data.get('current_price', 0.0),
                    "current_price": data.get('current_price', 0.0),
                    "change": data.get('change', 0.0),
                    "change_percent": data.get('change_percent', 0.0),
                    "previous_close": data.get('previous_close', 0.0),
                    "day_high": data.get('day_high', 0.0),
                    "day_low": data.get('day_low', 0.0),
                    "data_source": data.get('data_source', 'NSE/BSE Feed'),
                    "is_live": data.get('is_live', True)
                })
            else:
                results.append({
                    "symbol": item['symbol'],
                    "name": item['name'],
                    "exchange": item['exchange'],
                    "price": 0.0,
                    "current_price": 0.0,
                    "change": 0.0,
                    "change_percent": 0.0,
                    "previous_close": 0.0,
                    "day_high": 0.0,
                    "day_low": 0.0,
                    "data_source": "API Not Configured (Set UPSTOX_ACCESS_TOKEN in .env)",
                    "is_live": False
                })

        _INDICES_CACHE = {'data': results, 'timestamp': now}
        return results

    @staticmethod
    def get_stock_quote(symbol: str, is_index: bool = False):
        """
        Fetches the latest real market quote for an Indian stock or index.
        Prioritizes Upstox API v2 if credentials are configured in .env.
        """
        clean_symbol = InstrumentMappingService.normalize_symbol(symbol)
        cache_key = f"QUOTE_{clean_symbol}"
        now = time.time()

        if cache_key in _QUOTE_CACHE and (now - _QUOTE_CACHE[cache_key]['timestamp'] < CACHE_TTL):
            return _QUOTE_CACHE[cache_key]['data']

        # 1. Primary: Check if Upstox API is configured and symbol is not an index
        if UpstoxService.is_configured() and not symbol.startswith('^'):
            quote_data, msg, status = UpstoxService.fetch_market_quote(clean_symbol)
            if quote_data and status == 200:
                _QUOTE_CACHE[cache_key] = {'data': quote_data, 'timestamp': now}
                return quote_data

        # 2. Live Market Real Data Fetch
        instrument = InstrumentMappingService.get_instrument(symbol)
        yf_symbol = symbol if symbol.startswith('^') else f"{clean_symbol}.NS"

        try:
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info or {}
            
            current_price = (
                info.get('currentPrice') or 
                info.get('regularMarketPrice') or 
                info.get('previousClose') or 
                None
            )
            
            if current_price is None:
                # Try fetching fast history close
                hist = ticker.history(period='2d')
                if not hist.empty and len(hist) > 0:
                    current_price = float(hist['Close'].iloc[-1])
                    prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
                else:
                    if InstrumentMappingService.is_known_symbol(clean_symbol):
                        return StockService._get_unconfigured_quote(clean_symbol, instrument)
                    return None
            else:
                prev_close = (
                    info.get('previousClose') or 
                    info.get('regularMarketPreviousClose') or 
                    current_price
                )

            change = round_num(current_price - prev_close, 2) if (current_price and prev_close) else 0.0
            change_pct = round_num((change / prev_close) * 100, 2) if prev_close else 0.0

            comp_name = info.get('longName') or info.get('shortName') or instrument.get('name') or clean_symbol
            sector = info.get('sector') or instrument.get('sector') or 'Indian Equity'
            industry = info.get('industry') or instrument.get('industry') or 'Financial Markets'
            now_ist_str = datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')

            data_source_label = "Upstox Developer API v2" if UpstoxService.is_configured() else "NSE/BSE Live Feed (Upstox Token Pending in .env)"

            quote_data = {
                "symbol": clean_symbol if not symbol.startswith('^') else symbol,
                "name": comp_name,
                "instrument_key": instrument.get('instrument_key', f"NSE_EQ|{clean_symbol}"),
                "exchange": "BSE" if clean_symbol.endswith('.BO') or symbol == '^BSESN' else "NSE",
                "currency": "INR",
                "current_price": round_num(current_price, 2),
                "change": change,
                "change_percent": change_pct,
                "previous_close": round_num(prev_close, 2),
                "open": round_num(info.get('open') or info.get('regularMarketOpen') or current_price, 2),
                "day_high": round_num(info.get('dayHigh') or info.get('regularMarketDayHigh') or current_price, 2),
                "day_low": round_num(info.get('dayLow') or info.get('regularMarketDayLow') or current_price, 2),
                "volume": info.get('volume') or info.get('regularMarketVolume') or 0,
                "market_cap": info.get('marketCap'),
                "pe_ratio": round_num(info.get('trailingPE') or info.get('forwardPE'), 2),
                "fifty_two_week_high": round_num(info.get('fiftyTwoWeekHigh'), 2),
                "fifty_two_week_low": round_num(info.get('fiftyTwoWeekLow'), 2),
                "dividend_yield": round_num((info.get('dividendYield') or 0) * 100, 2) if info.get('dividendYield') else None,
                "beta": round_num(info.get('beta'), 2),
                "sector": sector,
                "industry": industry,
                "description": info.get('longBusinessSummary') or f"{comp_name} is an equity security listed on the National Stock Exchange of India (NSE).",
                "timestamp": now_ist_str,
                "data_source": data_source_label,
                "is_live": True,
                "is_demo": False
            }

            _QUOTE_CACHE[cache_key] = {'data': quote_data, 'timestamp': now}
            return quote_data

        except Exception as e:
            if InstrumentMappingService.is_known_symbol(clean_symbol):
                unconfigured = StockService._get_unconfigured_quote(clean_symbol, instrument)
                _QUOTE_CACHE[cache_key] = {'data': unconfigured, 'timestamp': now}
                return unconfigured
            return None

    @staticmethod
    def get_stock_history(symbol: str, range_period: str = '1mo', interval: str = '1d'):
        """
        Fetches historical price candles for charting.
        Prioritizes Upstox Historical Candle API if credentials are configured.
        """
        clean_symbol = InstrumentMappingService.normalize_symbol(symbol)
        cache_key = f"HIST_{clean_symbol}_{range_period.lower()}_{interval.lower()}"
        now = time.time()
        
        if cache_key in _HISTORY_CACHE:
            cached_entry = _HISTORY_CACHE[cache_key]
            if (now - cached_entry.get('timestamp', 0) < CACHE_TTL) and cached_entry.get('data', {}).get('points'):
                return cached_entry['data']

        # 1. Try Upstox API
        if UpstoxService.is_configured() and not symbol.startswith('^'):
            days_map = {
                '1d': 2, '1day': 2, '5d': 7, '1w': 7, '1wk': 7, 
                '1m': 30, '1mo': 30, '3m': 90, '3mo': 90, 
                '6m': 180, '6mo': 180, '1y': 365, '5y': 1825
            }
            r_days = days_map.get(range_period.lower(), 30)
            
            # Select appropriate candle interval for Upstox API based on the timeframe
            upstox_interval_map = {
                '1d': '30minute' if interval.lower() in ('1m', '5m', '15m', '30m') else '30minute',
                '1day': '30minute',
                '5d': 'day',
                '1w': 'day',
                '1wk': 'day',
                '1m': 'day',
                '1mo': 'day',
                '3m': 'day',
                '3mo': 'day',
                '6m': 'day',
                '6mo': 'day',
                '1y': 'day',
                '5y': 'week'
            }
            api_interval = upstox_interval_map.get(range_period.lower(), 'day')

            hist_data, msg, status = UpstoxService.fetch_historical_candles(clean_symbol, interval=api_interval, range_days=r_days)
            if hist_data and status == 200 and hist_data.get('points') and len(hist_data['points']) > 0:
                _HISTORY_CACHE[cache_key] = {'data': hist_data, 'timestamp': now}
                return hist_data

        # 2. Live Market Historical Feed
        yf_symbol = symbol if symbol.startswith('^') else f"{clean_symbol}.NS"
        period_map = {
            '1d': ('1d', '5m'),
            '1day': ('1d', '5m'),
            '5d': ('5d', '15m'),
            '1w': ('5d', '15m'),
            '1wk': ('5d', '15m'),
            '1m': ('1mo', '1d'),
            '1mo': ('1mo', '1d'),
            '3m': ('3mo', '1d'),
            '3mo': ('3mo', '1d'),
            '6m': ('6mo', '1d'),
            '6mo': ('6mo', '1d'),
            '1y': ('1y', '1d'),
            '5y': ('5y', '1wk')
        }
        yf_period, yf_interval = period_map.get(range_period.lower(), ('1mo', '1d'))

        try:
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period=yf_period, interval=yf_interval)
            
            if df.empty or len(df) == 0:
                history_data = {
                    "symbol": clean_symbol,
                    "period": range_period,
                    "interval": yf_interval,
                    "points": [],
                    "data_source": "No Historical Data Available",
                    "is_live": False
                }
            else:
                data_points = []
                for index, row in df.iterrows():
                    if isinstance(index, pd.Timestamp):
                        ts_str = index.strftime('%Y-%m-%d %H:%M') if yf_interval in ['1m', '5m', '15m', '30m'] else index.strftime('%Y-%m-%d')
                    else:
                        ts_str = str(index)[:10]

                    close_val = round_num(row.get('Close'), 2)
                    if close_val is not None and not pd.isna(close_val):
                        data_points.append({
                            "date": ts_str,
                            "open": round_num(row.get('Open'), 2) or close_val,
                            "high": round_num(row.get('High'), 2) or close_val,
                            "low": round_num(row.get('Low'), 2) or close_val,
                            "close": close_val,
                            "volume": int(row.get('Volume', 0)) if not pd.isna(row.get('Volume')) else 0
                        })
                    
                data_src = "Upstox Developer API v2" if UpstoxService.is_configured() else "NSE/BSE Historical Candle Feed"
                history_data = {
                    "symbol": clean_symbol,
                    "period": range_period,
                    "interval": yf_interval,
                    "points": data_points,
                    "data_source": data_src,
                    "is_live": True
                }
        except Exception:
            history_data = {
                "symbol": clean_symbol,
                "period": range_period,
                "interval": "1d",
                "points": [],
                "data_source": "API Not Configured (Set UPSTOX_ACCESS_TOKEN in .env)",
                "is_live": False
            }

        if history_data.get('points') and len(history_data['points']) > 0:
            _HISTORY_CACHE[cache_key] = {'data': history_data, 'timestamp': now}

        return history_data

    @staticmethod
    def _get_unconfigured_quote(symbol: str, instrument: dict = None):
        """Returns clean unconfigured state response without fake numbers."""
        if not instrument:
            instrument = InstrumentMappingService.get_instrument(symbol)
        comp_name = instrument.get('name', symbol)
        sector = instrument.get('sector', 'Indian Equity')
        industry = instrument.get('industry', 'NSE Listed')

        return {
            "symbol": symbol,
            "name": comp_name,
            "instrument_key": instrument.get('instrument_key', f"NSE_EQ|{symbol}"),
            "exchange": "NSE",
            "currency": "INR",
            "current_price": None,
            "change": None,
            "change_percent": None,
            "previous_close": None,
            "open": None,
            "day_high": None,
            "day_low": None,
            "volume": 0,
            "market_cap": None,
            "pe_ratio": None,
            "fifty_two_week_high": None,
            "fifty_two_week_low": None,
            "dividend_yield": None,
            "beta": None,
            "sector": sector,
            "industry": industry,
            "description": f"{comp_name} is listed on the National Stock Exchange of India (NSE).",
            "timestamp": datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST'),
            "data_source": "API Not Configured (Set UPSTOX_ACCESS_TOKEN in .env)",
            "is_live": False,
            "is_demo": False
        }
