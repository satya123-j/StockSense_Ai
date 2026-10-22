import os
import requests
import datetime
import urllib.parse
import pytz
from flask import current_app
from backend.app.services.instrument_mapping_service import InstrumentMappingService
from backend.app.utils.helpers import round_num

# IST Timezone for Indian Stock Exchanges (NSE / BSE)
IST = pytz.timezone('Asia/Kolkata')


class UpstoxService:
    """
    Communicates with the official Upstox Developer API v2 for Indian market quotes and historical candles.
    Documentation: https://upstox.com/developer/api-documentation/
    """

    @staticmethod
    def get_access_token() -> str:
        """Fetches access token from environment or app config."""
        token = os.getenv('UPSTOX_ACCESS_TOKEN', '')
        if not token and current_app:
            token = current_app.config.get('UPSTOX_ACCESS_TOKEN', '')
        return token.strip() if token else ''

    @staticmethod
    def get_client_id() -> str:
        """Fetches Upstox Client ID / API Key."""
        cid = os.getenv('UPSTOX_CLIENT_ID', '')
        if not cid and current_app:
            cid = current_app.config.get('UPSTOX_CLIENT_ID', '')
        return cid.strip() if cid else ''

    @staticmethod
    def get_client_secret() -> str:
        """Fetches Upstox Client Secret."""
        secret = os.getenv('UPSTOX_CLIENT_SECRET', '')
        if not secret and current_app:
            secret = current_app.config.get('UPSTOX_CLIENT_SECRET', '')
        return secret.strip() if secret else ''

    @staticmethod
    def get_redirect_uri() -> str:
        """Fetches registered redirect URI."""
        uri = os.getenv('UPSTOX_REDIRECT_URI', 'http://127.0.0.1:5000/api/auth/upstox/callback')
        if current_app:
            uri = current_app.config.get('UPSTOX_REDIRECT_URI', uri)
        return uri.strip() if uri else ''

    @staticmethod
    def get_base_url() -> str:
        """Fetches base API URL."""
        url = os.getenv('UPSTOX_BASE_URL', 'https://api.upstox.com/v2')
        if current_app:
            url = current_app.config.get('UPSTOX_BASE_URL', url)
        return url.rstrip('/')

    @staticmethod
    def is_configured() -> bool:
        """Returns True if the Upstox API access token is present in the environment."""
        token = UpstoxService.get_access_token()
        return bool(token and len(token) > 15)

    @staticmethod
    def get_login_url() -> str:
        """
        Generates Upstox OAuth 2.0 authorization dialog URL.
        User visits this URL to authenticate and grant access.
        """
        client_id = UpstoxService.get_client_id()
        redirect_uri = UpstoxService.get_redirect_uri()
        base_url = UpstoxService.get_base_url()

        params = {
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': redirect_uri
        }
        return f"{base_url}/login/authorization/dialog?{urllib.parse.urlencode(params)}"

    @staticmethod
    def exchange_code_for_token(auth_code: str) -> tuple[dict, str, int]:
        """
        Exchanges the authorization code from Upstox OAuth redirect for an API access token.
        Endpoint: POST /login/authorization/token
        """
        if not auth_code:
            return None, "Authorization code is required.", 400

        client_id = UpstoxService.get_client_id()
        client_secret = UpstoxService.get_client_secret()
        redirect_uri = UpstoxService.get_redirect_uri()

        if not client_id or not client_secret:
            return None, "UPSTOX_CLIENT_ID or UPSTOX_CLIENT_SECRET not configured in .env", 500

        url = f"{UpstoxService.get_base_url()}/login/authorization/token"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "code": auth_code.strip(),
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }

        try:
            response = requests.post(url, headers=headers, data=payload, timeout=10)
            data = response.json() if response.content else {}

            if response.status_code != 200:
                err_msg = data.get('message') or data.get('error') or f"Upstox token exchange returned HTTP {response.status_code}"
                return None, err_msg, response.status_code

            access_token = data.get('access_token')
            if not access_token:
                return None, "No access_token found in Upstox response.", 502

            return data, "Access token obtained successfully.", 200

        except requests.exceptions.RequestException as e:
            return None, f"Network error communicating with Upstox: {str(e)}", 502

    @staticmethod
    def get_market_session_status():
        """
        Determines Indian stock market session and trading hours status (NSE/BSE).
        Regular Trading Hours: Monday to Friday, 9:15 AM to 3:30 PM IST.
        Pre-market Session: 9:00 AM to 9:15 AM IST.
        Post-market Session: 3:30 PM to 4:00 PM IST.
        """
        now_ist = datetime.datetime.now(IST)
        weekday = now_ist.weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
        is_weekend = weekday >= 5

        time_now = now_ist.time()
        pre_market_open = datetime.time(9, 0)
        market_open = datetime.time(9, 15)
        market_close = datetime.time(15, 30)
        post_market_close = datetime.time(16, 0)

        if is_weekend:
            session_name = "Weekend (Market Closed)"
            is_open = False
        elif pre_market_open <= time_now < market_open:
            session_name = "Pre-Market Session"
            is_open = False
        elif market_open <= time_now <= market_close:
            session_name = "Regular Live Trading Session"
            is_open = True
        elif market_close < time_now <= post_market_close:
            session_name = "Post-Market Session"
            is_open = False
        else:
            session_name = "Post-Market / Closed"
            is_open = False

        return {
            "is_market_open": is_open,
            "current_time_ist": now_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
            "session_name": session_name,
            "trading_hours": "09:15 - 15:30 IST (Mon-Fri)",
            "api_configured": UpstoxService.is_configured()
        }

    @staticmethod
    def fetch_market_quote(symbol: str) -> tuple[dict, str, int]:
        """
        Fetches live real market quote for an Indian stock via Upstox MarketQuote API v2.
        Endpoint: GET /market-quote/quotes?instrument_key={key}
        """
        if not UpstoxService.is_configured():
            return None, "Upstox API access token is not configured in .env", 503

        instrument = InstrumentMappingService.get_instrument(symbol)
        instrument_key = instrument.get('instrument_key')

        url = f"{UpstoxService.get_base_url()}/market-quote/quotes"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {UpstoxService.get_access_token()}"
        }
        params = {"instrument_key": instrument_key}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=8)
            
            if response.status_code == 401:
                return None, "Upstox access token has expired or is invalid.", 401
            elif response.status_code == 429:
                return None, "Upstox API rate limit reached. Please retry in a moment.", 429
            elif response.status_code == 404:
                return None, f"Instrument {symbol} not found on Upstox API.", 404
            elif response.status_code != 200:
                return None, f"Upstox API returned status {response.status_code}", response.status_code

            data = response.json()
            quotes = data.get('data', {})
            
            # Format in Upstox response can be keyed by NSE_EQ:TCS, NSE_EQ|INE467B01029, etc.
            quote_payload = None
            for k, v in quotes.items():
                if (instrument_key in k or 
                    instrument['trading_symbol'] in k or 
                    instrument['symbol'] in k or 
                    k.endswith(f":{instrument['trading_symbol']}")):
                    quote_payload = v
                    break
            
            if not quote_payload and quotes:
                quote_payload = next(iter(quotes.values()))

            if not quote_payload:
                return None, f"No quote data returned from Upstox for {symbol}", 404

            # Normalize quote fields
            ohlc = quote_payload.get('ohlc', {})
            last_price = float(quote_payload.get('last_price') or ohlc.get('close') or 0.0)
            prev_close = float(ohlc.get('close') or quote_payload.get('prev_close') or last_price)
            open_price = float(ohlc.get('open') or last_price)
            day_high = float(ohlc.get('high') or last_price)
            day_low = float(ohlc.get('low') or last_price)
            volume = int(quote_payload.get('volume') or quote_payload.get('volume_traded') or 0)

            change = round_num(last_price - prev_close, 2) if (last_price and prev_close) else 0.0
            change_percent = round_num((change / prev_close) * 100, 2) if prev_close else 0.0

            normalized = {
                "symbol": instrument['trading_symbol'],
                "name": instrument['name'],
                "instrument_key": instrument_key,
                "exchange": instrument.get('exchange', 'NSE'),
                "currency": "INR",
                "current_price": round_num(last_price, 2),
                "previous_close": round_num(prev_close, 2),
                "open": round_num(open_price, 2),
                "day_high": round_num(day_high, 2),
                "day_low": round_num(day_low, 2),
                "volume": volume,
                "change": change,
                "change_percent": change_percent,
                "fifty_two_week_high": round_num(quote_payload.get('52_week_high') or quote_payload.get('fifty_two_week_high'), 2),
                "fifty_two_week_low": round_num(quote_payload.get('52_week_low') or quote_payload.get('fifty_two_week_low'), 2),
                "timestamp": quote_payload.get('timestamp') or datetime.datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST'),
                "sector": instrument.get('sector', 'Indian Equity'),
                "industry": instrument.get('industry', 'NSE Listed'),
                "data_source": "Upstox Developer API v2",
                "is_live": True,
                "is_demo": False
            }

            return normalized, "Success", 200

        except requests.exceptions.Timeout:
            return None, "Upstox API request timed out.", 504
        except requests.exceptions.RequestException as e:
            return None, f"Upstox API network error: {str(e)}", 502

    @staticmethod
    def fetch_historical_candles(symbol: str, interval: str = 'day', range_days: int = 30) -> tuple[dict, str, int]:
        """
        Fetches historical OHLC candle data from Upstox History API.
        Endpoint: GET /historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}
        Supported intervals: 1minute, 30minute, day, week, month
        """
        if not UpstoxService.is_configured():
            return None, "Upstox API access token is not configured in .env", 503

        instrument = InstrumentMappingService.get_instrument(symbol)
        instrument_key = instrument.get('instrument_key')

        now_ist = datetime.datetime.now(IST)
        to_date = now_ist.strftime('%Y-%m-%d')
        from_date = (now_ist - datetime.timedelta(days=range_days)).strftime('%Y-%m-%d')

        upstox_interval_map = {
            '1d': 'day',
            '1w': 'week',
            '1m': 'month',
            '1min': '1minute',
            '30min': '30minute',
            'day': 'day',
            'week': 'week',
            'month': 'month'
        }
        api_interval = upstox_interval_map.get(interval.lower(), 'day')

        encoded_instrument_key = urllib.parse.quote(str(instrument_key), safe='')
        url = f"{UpstoxService.get_base_url()}/historical-candle/{encoded_instrument_key}/{api_interval}/{to_date}/{from_date}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {UpstoxService.get_access_token()}"
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 401:
                return None, "Upstox access token has expired or is invalid.", 401
            elif response.status_code != 200:
                return None, f"Upstox Historical API returned status {response.status_code}", response.status_code

            data = response.json()
            candles = data.get('data', {}).get('candles', [])

            points = []
            # Upstox candle format: [timestamp, open, high, low, close, volume, open_interest]
            for c in candles:
                if len(c) >= 5:
                    ts_str = str(c[0])
                    date_part = ts_str[:10] if 'T' in ts_str else ts_str
                    points.append({
                        "date": date_part,
                        "open": round_num(float(c[1]), 2),
                        "high": round_num(float(c[2]), 2),
                        "low": round_num(float(c[3]), 2),
                        "close": round_num(float(c[4]), 2),
                        "volume": int(c[5]) if len(c) > 5 and c[5] is not None else 0
                    })

            # Sort ascending by date
            points.reverse()

            return {
                "symbol": instrument['trading_symbol'],
                "instrument_key": instrument_key,
                "interval": api_interval,
                "points": points,
                "data_source": "Upstox Developer API v2",
                "is_live": True
            }, "Success", 200

        except Exception as e:
            return None, f"Upstox Historical API error: {str(e)}", 502
