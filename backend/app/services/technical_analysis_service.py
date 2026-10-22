import pandas as pd
import numpy as np
import yfinance as yf
import datetime
import pytz
from backend.app.utils.helpers import round_num
from backend.app.services.instrument_mapping_service import InstrumentMappingService

IST = pytz.timezone('Asia/Kolkata')


class TechnicalAnalysisService:
    """
    Computes mathematical quantitative technical indicators using pandas & numpy
    from real historical market data.
    """

    @staticmethod
    def calculate_indicators(symbol: str, period: str = '1y'):
        """
        Fetches real historical candle data and computes:
        1. RSI (14-period Relative Strength Index)
        2. MACD (12-period Fast EMA, 26-period Slow EMA, 9-period Signal Line, Histogram)
        3. Moving Averages:
           - 20-period Simple Moving Average (SMA 20)
           - 50-period Simple Moving Average (SMA 50)
           - 200-period Simple Moving Average (SMA 200)
           - 20-period Exponential Moving Average (EMA 20)
        4. Classical Pivot Points (PP, R1, R2, S1, S2)

        Returns structured JSON with latest indicator values and chart series.
        """
        clean_symbol = InstrumentMappingService.normalize_symbol(symbol)
        yf_symbol = symbol if symbol.startswith('^') else f"{clean_symbol}.NS"
        now_ist_str = datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')

        try:
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period=period, interval='1d')
            
            if df.empty or len(df) < 5:
                return TechnicalAnalysisService._get_empty_technicals(clean_symbol, "Insufficient real historical data for indicator calculations.")
                
            # Clean dataframe
            df = df.dropna(subset=['Close'])
            if len(df) < 5:
                return TechnicalAnalysisService._get_empty_technicals(clean_symbol, "Insufficient real historical data points.")
            
            closes = df['Close']
            highs = df['High']
            lows = df['Low']
            volumes = df['Volume']

            # 1. Moving Averages (SMA 20, SMA 50, SMA 200, EMA 20)
            df['SMA_20'] = closes.rolling(window=20, min_periods=1).mean()
            df['SMA_50'] = closes.rolling(window=50, min_periods=1).mean()
            df['SMA_200'] = closes.rolling(window=200, min_periods=1).mean()
            df['EMA_20'] = closes.ewm(span=20, adjust=False).mean()

            # 2. RSI (14-period)
            if len(closes) >= 14:
                delta = closes.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
                rs = gain / (loss + 1e-9)
                df['RSI_14'] = 100 - (100 / (1 + rs))
            else:
                df['RSI_14'] = np.nan

            # 3. MACD (Fast=12, Slow=26, Signal=9)
            if len(closes) >= 12:
                ema12 = closes.ewm(span=12, adjust=False).mean()
                ema26 = closes.ewm(span=26, adjust=False).mean()
                df['MACD'] = ema12 - ema26
                df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
            else:
                df['MACD'] = np.nan
                df['MACD_Signal'] = np.nan
                df['MACD_Hist'] = np.nan

            # 4. Bollinger Bands (20, 2)
            bb_middle = df['SMA_20']
            bb_std = closes.rolling(window=20, min_periods=1).std().fillna(0)
            df['BB_Upper'] = bb_middle + (bb_std * 2)
            df['BB_Lower'] = bb_middle - (bb_std * 2)

            # Latest Values
            latest_close = float(closes.iloc[-1])
            latest_sma20 = float(df['SMA_20'].iloc[-1]) if not pd.isna(df['SMA_20'].iloc[-1]) else None
            latest_sma50 = float(df['SMA_50'].iloc[-1]) if not pd.isna(df['SMA_50'].iloc[-1]) else None
            latest_sma200 = float(df['SMA_200'].iloc[-1]) if not pd.isna(df['SMA_200'].iloc[-1]) else None
            latest_ema20 = float(df['EMA_20'].iloc[-1]) if not pd.isna(df['EMA_20'].iloc[-1]) else None
            latest_rsi = float(df['RSI_14'].iloc[-1]) if not pd.isna(df['RSI_14'].iloc[-1]) else None
            latest_macd = float(df['MACD'].iloc[-1]) if not pd.isna(df['MACD'].iloc[-1]) else None
            latest_macd_signal = float(df['MACD_Signal'].iloc[-1]) if not pd.isna(df['MACD_Signal'].iloc[-1]) else None
            latest_macd_hist = float(df['MACD_Hist'].iloc[-1]) if not pd.isna(df['MACD_Hist'].iloc[-1]) else None
            latest_bb_upper = float(df['BB_Upper'].iloc[-1]) if not pd.isna(df['BB_Upper'].iloc[-1]) else None
            latest_bb_lower = float(df['BB_Lower'].iloc[-1]) if not pd.isna(df['BB_Lower'].iloc[-1]) else None

            # Objective Indicator State Details (no subjective BUY/SELL claims)
            indicator_states = []

            if latest_rsi is not None:
                if latest_rsi >= 70:
                    rsi_state = "Overbought (> 70)"
                elif latest_rsi <= 30:
                    rsi_state = "Oversold (< 30)"
                elif latest_rsi >= 50:
                    rsi_state = "Positive Momentum (> 50)"
                else:
                    rsi_state = "Negative Momentum (< 50)"
                indicator_states.append({
                    "indicator": "RSI (14)",
                    "value": round_num(latest_rsi, 2),
                    "status": rsi_state,
                    "desc": f"14-period RSI calculated at {latest_rsi:.2f}"
                })

            if latest_macd is not None and latest_macd_signal is not None:
                crossover = "MACD > Signal Line" if latest_macd >= latest_macd_signal else "MACD < Signal Line"
                indicator_states.append({
                    "indicator": "MACD (12, 26, 9)",
                    "macd": round_num(latest_macd, 2),
                    "signal": round_num(latest_macd_signal, 2),
                    "histogram": round_num(latest_macd_hist, 2),
                    "status": crossover,
                    "desc": f"MACD line ({latest_macd:.2f}) vs Signal ({latest_macd_signal:.2f})"
                })

            if latest_sma20 is not None:
                ma_rel = "Price > SMA 20" if latest_close >= latest_sma20 else "Price < SMA 20"
                indicator_states.append({
                    "indicator": "SMA 20",
                    "value": round_num(latest_sma20, 2),
                    "status": ma_rel,
                    "desc": f"20-day Simple Moving Average at ₹{latest_sma20:.2f}"
                })

            if latest_sma50 is not None:
                ma50_rel = "SMA 20 > SMA 50" if (latest_sma20 and latest_sma20 >= latest_sma50) else "SMA 20 < SMA 50"
                indicator_states.append({
                    "indicator": "SMA 50",
                    "value": round_num(latest_sma50, 2),
                    "status": ma50_rel,
                    "desc": f"50-day Simple Moving Average at ₹{latest_sma50:.2f}"
                })

            # Classical Pivot Points
            prev_high = float(highs.iloc[-2]) if len(highs) > 1 else float(highs.iloc[-1])
            prev_low = float(lows.iloc[-2]) if len(lows) > 1 else float(lows.iloc[-1])
            prev_close = float(closes.iloc[-2]) if len(closes) > 1 else latest_close

            pivot = (prev_high + prev_low + prev_close) / 3.0
            r1 = (2 * pivot) - prev_low
            s1 = (2 * pivot) - prev_high
            r2 = pivot + (prev_high - prev_low)
            s2 = pivot - (prev_high - prev_low)

            # Historical Chart Series (last 60 trading sessions)
            series_tail = df.tail(60)
            time_series = []
            for idx, row in series_tail.iterrows():
                dt_str = idx.strftime('%Y-%m-%d') if isinstance(idx, pd.Timestamp) else str(idx)[:10]
                time_series.append({
                    "date": dt_str,
                    "close": round_num(row['Close'], 2),
                    "open": round_num(row.get('Open'), 2) if not pd.isna(row.get('Open')) else None,
                    "high": round_num(row.get('High'), 2) if not pd.isna(row.get('High')) else None,
                    "low": round_num(row.get('Low'), 2) if not pd.isna(row.get('Low')) else None,
                    "volume": int(row.get('Volume', 0)) if not pd.isna(row.get('Volume')) else 0,
                    "ma_20": round_num(row['SMA_20'], 2) if not pd.isna(row.get('SMA_20')) else None,
                    "ma_50": round_num(row['SMA_50'], 2) if not pd.isna(row.get('SMA_50')) else None,
                    "sma20": round_num(row['SMA_20'], 2) if not pd.isna(row.get('SMA_20')) else None,
                    "sma50": round_num(row['SMA_50'], 2) if not pd.isna(row.get('SMA_50')) else None,
                    "ema20": round_num(row['EMA_20'], 2) if not pd.isna(row.get('EMA_20')) else None,
                    "rsi": round_num(row['RSI_14'], 2) if not pd.isna(row.get('RSI_14')) else None,
                    "macd": round_num(row['MACD'], 2) if not pd.isna(row.get('MACD')) else None,
                    "macd_signal": round_num(row['MACD_Signal'], 2) if not pd.isna(row.get('MACD_Signal')) else None,
                    "macd_hist": round_num(row['MACD_Hist'], 2) if not pd.isna(row.get('MACD_Hist')) else None,
                    "bb_upper": round_num(row['BB_Upper'], 2) if not pd.isna(row.get('BB_Upper')) else None,
                    "bb_lower": round_num(row['BB_Lower'], 2) if not pd.isna(row.get('BB_Lower')) else None
                })

            return {
                "symbol": clean_symbol,
                "timestamp": now_ist_str,
                "latest": {
                    "rsi": round_num(latest_rsi, 2) if latest_rsi is not None else None,
                    "macd": round_num(latest_macd, 2) if latest_macd is not None else None,
                    "macd_signal": round_num(latest_macd_signal, 2) if latest_macd_signal is not None else None,
                    "macd_histogram": round_num(latest_macd_hist, 2) if latest_macd_hist is not None else None,
                    "ma_20": round_num(latest_sma20, 2) if latest_sma20 is not None else None,
                    "ma_50": round_num(latest_sma50, 2) if latest_sma50 is not None else None,
                    "close": round_num(latest_close, 2)
                },
                "summary_indicators": {
                    "rsi_14": round_num(latest_rsi, 2) if latest_rsi is not None else None,
                    "sma_20": round_num(latest_sma20, 2) if latest_sma20 is not None else None,
                    "sma_50": round_num(latest_sma50, 2) if latest_sma50 is not None else None,
                    "sma_200": round_num(latest_sma200, 2) if latest_sma200 is not None else None,
                    "ema_20": round_num(latest_ema20, 2) if latest_ema20 is not None else None,
                    "macd": round_num(latest_macd, 2) if latest_macd is not None else None,
                    "macd_signal": round_num(latest_macd_signal, 2) if latest_macd_signal is not None else None,
                    "macd_hist": round_num(latest_macd_hist, 2) if latest_macd_hist is not None else None,
                    "bb_upper": round_num(latest_bb_upper, 2) if latest_bb_upper is not None else None,
                    "bb_middle": round_num(latest_sma20, 2) if latest_sma20 is not None else None,
                    "bb_lower": round_num(latest_bb_lower, 2) if latest_bb_lower is not None else None
                },
                "pivot_points": {
                    "pivot": round_num(pivot, 2),
                    "resistance_1": round_num(r1, 2),
                    "resistance_2": round_num(r2, 2),
                    "support_1": round_num(s1, 2),
                    "support_2": round_num(s2, 2)
                },
                "indicator_states": indicator_states,
                "signals": indicator_states,
                "chart_series": time_series,
                "series": time_series,
                "is_demo": False,
                "error": None
            }

        except Exception as e:
            return TechnicalAnalysisService._get_empty_technicals(clean_symbol, str(e))

    @staticmethod
    def _get_empty_technicals(symbol: str, message: str = "Data unavailable"):
        """Returns clean empty state for indicators without presenting mock numbers."""
        return {
            "symbol": symbol,
            "timestamp": datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST'),
            "latest": {
                "rsi": None,
                "macd": None,
                "macd_signal": None,
                "macd_histogram": None,
                "ma_20": None,
                "ma_50": None,
                "close": None
            },
            "summary_indicators": {
                "rsi_14": None,
                "sma_20": None,
                "sma_50": None,
                "sma_200": None,
                "ema_20": None,
                "macd": None,
                "macd_signal": None,
                "macd_hist": None,
                "bb_upper": None,
                "bb_middle": None,
                "bb_lower": None
            },
            "pivot_points": {
                "pivot": None,
                "resistance_1": None,
                "resistance_2": None,
                "support_1": None,
                "support_2": None
            },
            "indicator_states": [],
            "signals": [],
            "chart_series": [],
            "series": [],
            "error": message,
            "is_demo": False
        }
