from backend.app.extensions import db
from backend.app.models.watchlist import Watchlist
from backend.app.services.stock_service import StockService
from backend.app.services.instrument_mapping_service import InstrumentMappingService

class WatchlistService:
    """Service handling watchlist operations and live price updates."""

    @staticmethod
    def get_watchlist(user_id: int):
        """
        Fetches all stocks in the user's watchlist and enriches them
        with current market quotes.
        """
        items = Watchlist.query.filter_by(user_id=user_id).order_by(Watchlist.added_at.desc()).all()
        enriched = []

        for item in items:
            item_dict = item.to_dict()
            quote = StockService.get_stock_quote(item.symbol)
            if quote:
                item_dict['current_price'] = quote.get('current_price', 0.0)
                item_dict['change'] = quote.get('change', 0.0)
                item_dict['change_percent'] = quote.get('change_percent', 0.0)
                item_dict['day_high'] = quote.get('day_high', 0.0)
                item_dict['day_low'] = quote.get('day_low', 0.0)
                item_dict['sector'] = quote.get('sector', 'N/A')
                item_dict['data_source'] = quote.get('data_source', 'Upstox / NSE')
            else:
                item_dict['current_price'] = 0.0
                item_dict['change'] = 0.0
                item_dict['change_percent'] = 0.0
                item_dict['sector'] = 'N/A'
                item_dict['data_source'] = 'Offline'

            enriched.append(item_dict)

        return enriched

    @staticmethod
    def add_stock(user_id: int, symbol: str, company_name: str = None, notes: str = None) -> tuple[dict, str, int]:
        """Adds a stock to the user's watchlist."""
        clean_symbol = InstrumentMappingService.normalize_symbol(symbol) if not symbol.startswith('^') else symbol

        # Check if already in watchlist
        existing = Watchlist.query.filter(
            Watchlist.user_id == user_id,
            (Watchlist.symbol == clean_symbol) | (Watchlist.symbol == f"{clean_symbol}.NS")
        ).first()
        if existing:
            return None, f"Stock {clean_symbol} is already in your watchlist.", 409

        # If company name is not provided, fetch from quote/universe
        if not company_name:
            quote = StockService.get_stock_quote(clean_symbol)
            company_name = quote.get('name', clean_symbol)

        exchange = 'BSE' if symbol.endswith('.BO') else 'NSE'

        item = Watchlist(
            user_id=user_id,
            symbol=clean_symbol,
            company_name=company_name,
            exchange=exchange,
            notes=notes or ''
        )

        db.session.add(item)
        db.session.commit()

        return item.to_dict(), f"{clean_symbol} successfully added to your watchlist.", 201

    @staticmethod
    def remove_stock(user_id: int, item_id: int = None, symbol: str = None) -> tuple[bool, str, int]:
        """Removes a stock from user watchlist by ID or Symbol."""
        if item_id:
            item = Watchlist.query.filter_by(id=item_id, user_id=user_id).first()
        elif symbol:
            clean_symbol = InstrumentMappingService.normalize_symbol(symbol) if not symbol.startswith('^') else symbol
            item = Watchlist.query.filter(
                Watchlist.user_id == user_id,
                (Watchlist.symbol == clean_symbol) | (Watchlist.symbol == f"{clean_symbol}.NS")
            ).first()
        else:
            return False, "Watchlist item ID or Symbol is required.", 400

        if not item:
            return False, "Watchlist item not found.", 404

        db.session.delete(item)
        db.session.commit()
        return True, "Stock removed from watchlist.", 200

    @staticmethod
    def check_is_in_watchlist(user_id: int, symbol: str) -> bool:
        """Returns True if the stock is in user's watchlist."""
        if not symbol or not user_id:
            return False
        clean_symbol = InstrumentMappingService.normalize_symbol(symbol) if not symbol.startswith('^') else symbol
        return Watchlist.query.filter(
            Watchlist.user_id == user_id,
            (Watchlist.symbol == clean_symbol) | (Watchlist.symbol == f"{clean_symbol}.NS")
        ).first() is not None
