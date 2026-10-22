import os
import json

# Comprehensive Indian Stock Universe with official NSE ISIN and Upstox Instrument Keys
NSE_INSTRUMENTS_MASTER = [
    {
        "symbol": "TCS",
        "trading_symbol": "TCS",
        "instrument_key": "NSE_EQ|INE467B01029",
        "isin": "INE467B01029",
        "name": "Tata Consultancy Services Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Information Technology",
        "industry": "IT Services"
    },
    {
        "symbol": "INFY",
        "trading_symbol": "INFY",
        "instrument_key": "NSE_EQ|INE009A01021",
        "isin": "INE009A01021",
        "name": "Infosys Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Information Technology",
        "industry": "IT Services"
    },
    {
        "symbol": "RELIANCE",
        "trading_symbol": "RELIANCE",
        "instrument_key": "NSE_EQ|INE002A01018",
        "isin": "INE002A01018",
        "name": "Reliance Industries Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Energy & Petrochemicals",
        "industry": "Oil & Gas Refining"
    },
    {
        "symbol": "HDFCBANK",
        "trading_symbol": "HDFCBANK",
        "instrument_key": "NSE_EQ|INE040A01034",
        "isin": "INE040A01034",
        "name": "HDFC Bank Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Financial Services",
        "industry": "Private Banking"
    },
    {
        "symbol": "ICICIBANK",
        "trading_symbol": "ICICIBANK",
        "instrument_key": "NSE_EQ|INE090A01021",
        "isin": "INE090A01021",
        "name": "ICICI Bank Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Financial Services",
        "industry": "Private Banking"
    },
    {
        "symbol": "ITC",
        "trading_symbol": "ITC",
        "instrument_key": "NSE_EQ|INE154A01025",
        "isin": "INE154A01025",
        "name": "ITC Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Consumer Goods",
        "industry": "FMCG & Diversified"
    },
    {
        "symbol": "SBIN",
        "trading_symbol": "SBIN",
        "instrument_key": "NSE_EQ|INE062A01020",
        "isin": "INE062A01020",
        "name": "State Bank of India",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Financial Services",
        "industry": "Public Sector Banking"
    },
    {
        "symbol": "BHARTIARTL",
        "trading_symbol": "BHARTIARTL",
        "instrument_key": "NSE_EQ|INE397D01024",
        "isin": "INE397D01024",
        "name": "Bharti Airtel Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Telecommunications",
        "industry": "Telecom Services"
    },
    {
        "symbol": "TATAMOTORS",
        "trading_symbol": "TATAMOTORS",
        "instrument_key": "NSE_EQ|INE155A01022",
        "isin": "INE155A01022",
        "name": "Tata Motors Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Automobile",
        "industry": "Commercial & Passenger Vehicles"
    },
    {
        "symbol": "KOTAKBANK",
        "trading_symbol": "KOTAKBANK",
        "instrument_key": "NSE_EQ|INE237A01028",
        "isin": "INE237A01028",
        "name": "Kotak Mahindra Bank Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Financial Services",
        "industry": "Private Banking"
    },
    {
        "symbol": "LT",
        "trading_symbol": "LT",
        "instrument_key": "NSE_EQ|INE018A01030",
        "isin": "INE018A01030",
        "name": "Larsen & Toubro Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Capital Goods",
        "industry": "Engineering & Infrastructure"
    },
    {
        "symbol": "HINDUNILVR",
        "trading_symbol": "HINDUNILVR",
        "instrument_key": "NSE_EQ|INE030A01027",
        "isin": "INE030A01027",
        "name": "Hindustan Unilever Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Consumer Goods",
        "industry": "FMCG"
    },
    {
        "symbol": "AXISBANK",
        "trading_symbol": "AXISBANK",
        "instrument_key": "NSE_EQ|INE238A01034",
        "isin": "INE238A01034",
        "name": "Axis Bank Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Financial Services",
        "industry": "Private Banking"
    },
    {
        "symbol": "MARUTI",
        "trading_symbol": "MARUTI",
        "instrument_key": "NSE_EQ|INE585B01010",
        "isin": "INE585B01010",
        "name": "Maruti Suzuki India Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Automobile",
        "industry": "Passenger Cars"
    },
    {
        "symbol": "SUNPHARMA",
        "trading_symbol": "SUNPHARMA",
        "instrument_key": "NSE_EQ|INE044A01036",
        "isin": "INE044A01036",
        "name": "Sun Pharmaceutical Industries Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Healthcare",
        "industry": "Pharmaceuticals"
    },
    {
        "symbol": "BAJFINANCE",
        "trading_symbol": "BAJFINANCE",
        "instrument_key": "NSE_EQ|INE296A01024",
        "isin": "INE296A01024",
        "name": "Bajaj Finance Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Financial Services",
        "industry": "NBFC"
    },
    {
        "symbol": "WIPRO",
        "trading_symbol": "WIPRO",
        "instrument_key": "NSE_EQ|INE075A01022",
        "isin": "INE075A01022",
        "name": "Wipro Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Information Technology",
        "industry": "IT Services"
    },
    {
        "symbol": "ASIANPAINT",
        "trading_symbol": "ASIANPAINT",
        "instrument_key": "NSE_EQ|INE021A01026",
        "isin": "INE021A01026",
        "name": "Asian Paints Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Consumer Durables",
        "industry": "Paints"
    },
    {
        "symbol": "TITAN",
        "trading_symbol": "TITAN",
        "instrument_key": "NSE_EQ|INE280A01028",
        "isin": "INE280A01028",
        "name": "Titan Company Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Consumer Goods",
        "industry": "Gems & Jewellery"
    },
    {
        "symbol": "TATASTEEL",
        "trading_symbol": "TATASTEEL",
        "instrument_key": "NSE_EQ|INE081A01020",
        "isin": "INE081A01020",
        "name": "Tata Steel Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Metals & Mining",
        "industry": "Steel Manufacturing"
    },
    {
        "symbol": "NTPC",
        "trading_symbol": "NTPC",
        "instrument_key": "NSE_EQ|INE733E01010",
        "isin": "INE733E01010",
        "name": "NTPC Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Utilities",
        "industry": "Power Generation"
    },
    {
        "symbol": "POWERGRID",
        "trading_symbol": "POWERGRID",
        "instrument_key": "NSE_EQ|INE752E01010",
        "isin": "INE752E01010",
        "name": "Power Grid Corporation of India Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Utilities",
        "industry": "Power Transmission"
    },
    {
        "symbol": "ONGC",
        "trading_symbol": "ONGC",
        "instrument_key": "NSE_EQ|INE213A01029",
        "isin": "INE213A01029",
        "name": "Oil & Natural Gas Corporation Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Energy",
        "industry": "Oil & Gas Exploration"
    },
    {
        "symbol": "COALINDIA",
        "trading_symbol": "COALINDIA",
        "instrument_key": "NSE_EQ|INE522F01014",
        "isin": "INE522F01014",
        "name": "Coal India Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Metals & Mining",
        "industry": "Coal Production"
    },
    {
        "symbol": "BAJAJFINSV",
        "trading_symbol": "BAJAJFINSV",
        "instrument_key": "NSE_EQ|INE918I01018",
        "isin": "INE918I01018",
        "name": "Bajaj Finserv Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Financial Services",
        "industry": "Diversified Financials"
    },
    {
        "symbol": "NESTLEIND",
        "trading_symbol": "NESTLEIND",
        "instrument_key": "NSE_EQ|INE239A01016",
        "isin": "INE239A01016",
        "name": "Nestle India Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Consumer Goods",
        "industry": "Food & Beverages"
    },
    {
        "symbol": "ULTRACEMCO",
        "trading_symbol": "ULTRACEMCO",
        "instrument_key": "NSE_EQ|INE481G01011",
        "isin": "INE481G01011",
        "name": "UltraTech Cement Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Construction Materials",
        "industry": "Cement"
    },
    {
        "symbol": "JSWSTEEL",
        "trading_symbol": "JSWSTEEL",
        "instrument_key": "NSE_EQ|INE019A01038",
        "isin": "INE019A01038",
        "name": "JSW Steel Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Metals & Mining",
        "industry": "Steel Manufacturing"
    },
    {
        "symbol": "ADANIENT",
        "trading_symbol": "ADANIENT",
        "instrument_key": "NSE_EQ|INE423A01024",
        "isin": "INE423A01024",
        "name": "Adani Enterprises Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Diversified",
        "industry": "Commodities & Trading"
    },
    {
        "symbol": "ADANIPORTS",
        "trading_symbol": "ADANIPORTS",
        "instrument_key": "NSE_EQ|INE742F01042",
        "isin": "INE742F01042",
        "name": "Adani Ports and Special Economic Zone Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Services",
        "industry": "Port Infrastructure"
    },
    {
        "symbol": "ZOMATO",
        "trading_symbol": "ZOMATO",
        "instrument_key": "NSE_EQ|INE758T01015",
        "isin": "INE758T01015",
        "name": "Zomato Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Consumer Tech",
        "industry": "Food Delivery & Platforms"
    },
    {
        "symbol": "TECHM",
        "trading_symbol": "TECHM",
        "instrument_key": "NSE_EQ|INE669C01036",
        "isin": "INE669C01036",
        "name": "Tech Mahindra Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Information Technology",
        "industry": "IT Services"
    },
    {
        "symbol": "HCLTECH",
        "trading_symbol": "HCLTECH",
        "instrument_key": "NSE_EQ|INE860A01027",
        "isin": "INE860A01027",
        "name": "HCL Technologies Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Information Technology",
        "industry": "IT Services"
    },
    {
        "symbol": "TRENT",
        "trading_symbol": "TRENT",
        "instrument_key": "NSE_EQ|INE849A01020",
        "isin": "INE849A01020",
        "name": "Trent Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Consumer Services",
        "industry": "Retail & Fashion"
    },
    {
        "symbol": "JIOFIN",
        "trading_symbol": "JIOFIN",
        "instrument_key": "NSE_EQ|INE758E01017",
        "isin": "INE758E01017",
        "name": "Jio Financial Services Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Financial Services",
        "industry": "Financial Services"
    },
    {
        "symbol": "BEL",
        "trading_symbol": "BEL",
        "instrument_key": "NSE_EQ|INE263A01024",
        "isin": "INE263A01024",
        "name": "Bharat Electronics Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Capital Goods",
        "industry": "Aerospace & Defense Electronics"
    },
    {
        "symbol": "HAL",
        "trading_symbol": "HAL",
        "instrument_key": "NSE_EQ|INE066F01012",
        "isin": "INE066F01012",
        "name": "Hindustan Aeronautics Ltd",
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "sector": "Capital Goods",
        "industry": "Aerospace & Defense"
    }
]

# Benchmark Indices Mapping
BENCHMARK_INDICES_MASTER = [
    {
        "symbol": "NIFTY50",
        "trading_symbol": "NIFTY 50",
        "instrument_key": "NSE_INDEX|Nifty 50",
        "name": "NIFTY 50",
        "exchange": "NSE",
        "segment": "NSE_INDEX"
    },
    {
        "symbol": "BANKNIFTY",
        "trading_symbol": "NIFTY BANK",
        "instrument_key": "NSE_INDEX|Nifty Bank",
        "name": "NIFTY BANK",
        "exchange": "NSE",
        "segment": "NSE_INDEX"
    },
    {
        "symbol": "SENSEX",
        "trading_symbol": "BSE SENSEX",
        "instrument_key": "BSE_INDEX|SENSEX",
        "name": "BSE SENSEX",
        "exchange": "BSE",
        "segment": "BSE_INDEX"
    },
    {
        "symbol": "NIFTYIT",
        "trading_symbol": "NIFTY IT",
        "instrument_key": "NSE_INDEX|Nifty IT",
        "name": "NIFTY IT",
        "exchange": "NSE",
        "segment": "NSE_INDEX"
    }
]


class InstrumentMappingService:
    """Service that resolves and maps Indian stock symbols to Upstox exchange instrument keys."""

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """Strips exchange suffixes like .NS, .BO or whitespace."""
        if not symbol:
            return ""
        s = symbol.strip().upper()
        s = s.replace('.NS', '').replace('.BO', '')
        return s

    @staticmethod
    def get_instrument(symbol: str):
        """
        Retrieves instrument details for a symbol (e.g. TCS, INFY, RELIANCE).
        """
        clean_sym = InstrumentMappingService.normalize_symbol(symbol)
        
        # Check standard equity universe
        for item in NSE_INSTRUMENTS_MASTER:
            if (item['symbol'] == clean_sym or 
                item['trading_symbol'] == clean_sym or 
                item['isin'] == clean_sym or 
                item['instrument_key'] == symbol):
                return item

        # Check indices
        for idx in BENCHMARK_INDICES_MASTER:
            if (idx['symbol'] == clean_sym or 
                idx['trading_symbol'] == clean_sym or 
                idx['instrument_key'] == symbol or
                (symbol.startswith('^') and clean_sym in idx['symbol'])):
                return idx

        # Generate generic NSE equity mapping for any searched symbol
        return {
            "symbol": clean_sym,
            "trading_symbol": clean_sym,
            "instrument_key": f"NSE_EQ|{clean_sym}",
            "isin": "",
            "name": clean_sym,
            "exchange": "NSE",
            "segment": "NSE_EQ",
            "sector": "Indian Equities",
            "industry": "NSE Listed"
        }

    @staticmethod
    def is_known_symbol(symbol: str) -> bool:
        """Returns True if the symbol is in our master list of Indian instruments or benchmark indices."""
        clean_sym = InstrumentMappingService.normalize_symbol(symbol)
        for item in NSE_INSTRUMENTS_MASTER:
            if (item['symbol'].upper() == clean_sym or 
                item['trading_symbol'].upper() == clean_sym or 
                item['isin'].upper() == clean_sym):
                return True
        for idx in BENCHMARK_INDICES_MASTER:
            if (idx['symbol'].upper() == clean_sym or 
                idx['trading_symbol'].upper() == clean_sym or 
                (symbol.startswith('^') and clean_sym in idx['symbol'].upper())):
                return True
        return False

    @staticmethod
    def get_instrument_key(symbol: str) -> str:
        """Returns the specific Upstox instrument key (e.g. NSE_EQ|INE467B01029)."""
        inst = InstrumentMappingService.get_instrument(symbol)
        return inst.get('instrument_key', f"NSE_EQ|{InstrumentMappingService.normalize_symbol(symbol)}")

    @staticmethod
    def search_instruments(query: str, limit: int = 10):
        """
        Fuzzy search for Indian stocks by symbol or company name.
        """
        if not query:
            return NSE_INSTRUMENTS_MASTER[:limit]

        q = query.strip().upper()
        results = []

        # 1. Exact or prefix symbol match
        for item in NSE_INSTRUMENTS_MASTER:
            if q == item['symbol'] or item['symbol'].startswith(q):
                results.append(item)

        # 2. Company name or sector match
        for item in NSE_INSTRUMENTS_MASTER:
            if item not in results and (q in item['name'].upper() or q in item['sector'].upper()):
                results.append(item)

        # 3. Dynamic match if user searches arbitrary valid symbol
        if not results and len(query) >= 2:
            clean_q = InstrumentMappingService.normalize_symbol(query)
            results.append({
                "symbol": clean_q,
                "trading_symbol": clean_q,
                "instrument_key": f"NSE_EQ|{clean_q}",
                "isin": "",
                "name": clean_q,
                "exchange": "NSE",
                "segment": "NSE_EQ",
                "sector": "Indian Market (NSE)",
                "industry": "Equity"
            })

        return results[:limit]
