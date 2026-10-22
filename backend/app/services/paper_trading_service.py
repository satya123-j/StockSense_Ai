from datetime import datetime
from backend.app.extensions import db
from backend.app.models.portfolio import Holding, Transaction
from backend.app.services.wallet_service import WalletService
from backend.app.services.stock_service import StockService
from backend.app.services.instrument_mapping_service import InstrumentMappingService

class PaperTradingService:
    """Service handling simulated paper trading buy/sell operations."""

    @staticmethod
    def buy_stock(user_id: int, symbol: str, quantity: int) -> tuple[dict, str, int]:
        """
        Executes a simulated paper-trading BUY order:
        1. Validates quantity (positive integer) and symbol.
        2. Retrieves live market price from StockService.
        3. Calculates total_cost = current_price * quantity.
        4. Checks user's virtual wallet.
        5. Rejects if insufficient cash.
        6. Deducts total_cost from user's virtual wallet.
        7. Creates/updates holding with weighted average buy price.
        8. Creates transaction record.
        9. Returns updated balance and holding.
        """
        # 1. Validate quantity
        try:
            qty = int(quantity)
            if qty <= 0:
                return None, "Quantity must be a positive whole integer greater than zero.", 400
        except (ValueError, TypeError):
            return None, "Invalid quantity specified. Must be an integer.", 400

        # 2. Validate symbol
        if not symbol or not isinstance(symbol, str):
            return None, "Stock symbol is required.", 400

        clean_symbol = InstrumentMappingService.normalize_symbol(symbol.strip().upper())
        if not clean_symbol:
            return None, "Invalid stock symbol format.", 400

        # 3. Retrieve authoritative market price from StockService (backend authority)
        quote = StockService.get_stock_quote(clean_symbol)
        if not quote or not quote.get('current_price') or float(quote.get('current_price', 0)) <= 0:
            return None, f"Unable to fetch valid market price for '{clean_symbol}'.", 400

        current_price = round(float(quote['current_price']), 2)
        company_name = quote.get('name') or clean_symbol
        exchange = quote.get('exchange') or 'NSE'

        # 4. Calculate actual total cost on backend
        total_cost = round(current_price * qty, 2)

        # 5. Check user's separate virtual wallet
        wallet = WalletService.get_or_create_wallet(user_id)
        if wallet.virtual_cash < total_cost:
            return None, (
                f"Insufficient virtual funds to complete purchase. "
                f"Required: ₹{total_cost:,.2f} ({qty} shares @ ₹{current_price:,.2f}), "
                f"Available: ₹{wallet.virtual_cash:,.2f}."
            ), 400

        # 6. Deduct total_cost from this user's virtual cash
        wallet.virtual_cash = round(wallet.virtual_cash - total_cost, 2)
        wallet.updated_at = datetime.utcnow()

        # 7. Create or update portfolio holding
        holding = Holding.query.filter_by(user_id=user_id, symbol=clean_symbol).first()
        if holding:
            # Weighted average price formula:
            # ((existing_qty * existing_avg_price) + (new_qty * current_price)) / (existing_qty + new_qty)
            old_invested = holding.quantity * holding.average_buy_price
            added_invested = qty * current_price
            new_total_qty = holding.quantity + qty
            new_avg_price = round((old_invested + added_invested) / new_total_qty, 2)

            holding.quantity = new_total_qty
            holding.average_buy_price = new_avg_price
            holding.total_invested = round(new_total_qty * new_avg_price, 2)
            holding.company_name = company_name
            holding.exchange = exchange
            holding.updated_at = datetime.utcnow()
        else:
            holding = Holding(
                user_id=user_id,
                symbol=clean_symbol,
                company_name=company_name,
                exchange=exchange,
                quantity=qty,
                average_buy_price=current_price,
                total_invested=total_cost,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(holding)

        # 8. Create BUY transaction record
        tx = Transaction(
            user_id=user_id,
            symbol=clean_symbol,
            company_name=company_name,
            transaction_type='BUY',
            quantity=qty,
            price=current_price,
            total_amount=total_cost,
            realized_pnl=0.0,
            status='COMPLETED',
            created_at=datetime.utcnow()
        )
        db.session.add(tx)

        db.session.commit()

        return {
            'wallet': wallet.to_dict(),
            'holding': holding.to_dict(),
            'transaction': tx.to_dict()
        }, f"Successfully purchased {qty} share(s) of {clean_symbol} at ₹{current_price:,.2f}.", 200

    @staticmethod
    def sell_stock(user_id: int, symbol: str, quantity: int) -> tuple[dict, str, int]:
        """
        Executes a simulated paper-trading SELL order:
        1. Identifies the authenticated user.
        2. Validates positive integer quantity and symbol.
        3. Verifies that the user owns the stock.
        4. Verifies that the user has enough quantity to sell (cannot sell more than owned).
        5. Fetches live market price from existing StockService (backend authority).
        6. Calculates: sell_value = current_price * quantity.
        7. Calculates realized profit/loss:
           cost_basis = holding.average_buy_price * quantity
           realized_pnl = sell_value - cost_basis
        8. Adds sell_value to user's virtual cash wallet.
        9. Reduces holding quantity.
        10. If quantity becomes zero, deletes/closes the holding.
        11. Creates a SELL transaction record with realized P&L.
        12. Returns updated wallet balance, holding info, and transaction.
        """
        # 1. Validate quantity
        try:
            if isinstance(quantity, str):
                if not quantity.strip().isdigit():
                    return None, "Quantity must be a positive whole integer.", 400
                qty = int(quantity.strip())
            elif isinstance(quantity, int):
                qty = quantity
            elif isinstance(quantity, float):
                if not quantity.is_integer():
                    return None, "Quantity must be a whole integer.", 400
                qty = int(quantity)
            else:
                return None, "Invalid quantity specified. Must be an integer.", 400

            if qty <= 0:
                return None, "Quantity must be a positive whole integer greater than zero.", 400
        except (ValueError, TypeError):
            return None, "Invalid quantity specified. Must be an integer.", 400

        # 2. Validate symbol
        if not symbol or not isinstance(symbol, str):
            return None, "Stock symbol is required.", 400

        clean_symbol = InstrumentMappingService.normalize_symbol(symbol.strip().upper())
        if not clean_symbol:
            return None, "Invalid stock symbol format.", 400

        # 3. Verify user owns the stock
        holding = Holding.query.filter_by(user_id=user_id, symbol=clean_symbol).first()
        if not holding or holding.quantity <= 0:
            return None, f"You do not own any shares of '{clean_symbol}' to sell.", 400

        # 4. Verify user has enough quantity to sell
        if qty > holding.quantity:
            return None, (
                f"Cannot sell more shares than owned. You currently own {holding.quantity} share(s) "
                f"of {clean_symbol}, but requested to sell {qty}."
            ), 400

        # 5. Fetch authoritative live market price from StockService
        quote = StockService.get_stock_quote(clean_symbol)
        if not quote or not quote.get('current_price') or float(quote.get('current_price', 0)) <= 0:
            return None, f"Unable to fetch valid market price for '{clean_symbol}'.", 400

        current_price = round(float(quote['current_price']), 2)
        company_name = quote.get('name') or holding.company_name or clean_symbol

        # 6. Calculate sell value and realized profit/loss
        sell_value = round(current_price * qty, 2)
        cost_basis = round(holding.average_buy_price * qty, 2)
        realized_pnl = round(sell_value - cost_basis, 2)
        avg_price = holding.average_buy_price

        # 7. Add sell value to user's virtual cash
        wallet = WalletService.get_or_create_wallet(user_id)
        wallet.virtual_cash = round(wallet.virtual_cash + sell_value, 2)
        wallet.updated_at = datetime.utcnow()

        # 8. Reduce holding quantity; if zero, remove/close the holding
        remaining_qty = holding.quantity - qty
        closed = False
        holding_dict = None

        if remaining_qty == 0:
            closed = True
            db.session.delete(holding)
        else:
            holding.quantity = remaining_qty
            holding.total_invested = round(remaining_qty * holding.average_buy_price, 2)
            holding.updated_at = datetime.utcnow()
            holding_dict = holding.to_dict()

        # 9. Create SELL transaction record
        tx = Transaction(
            user_id=user_id,
            symbol=clean_symbol,
            company_name=company_name,
            transaction_type='SELL',
            quantity=qty,
            price=current_price,
            total_amount=sell_value,
            realized_pnl=realized_pnl,
            status='COMPLETED',
            created_at=datetime.utcnow()
        )
        db.session.add(tx)

        db.session.commit()

        pnl_sign = "+" if realized_pnl >= 0 else "-"
        pnl_desc = f"{pnl_sign}₹{abs(realized_pnl):,.2f}"
        msg = f"Successfully sold {qty} share(s) of {clean_symbol} at ₹{current_price:,.2f} (Realized P&L: {pnl_desc})."

        return {
            'wallet': wallet.to_dict(),
            'holding': holding_dict,
            'is_closed': closed,
            'remaining_quantity': remaining_qty,
            'transaction': tx.to_dict(),
            'sell_value': sell_value,
            'realized_pnl': realized_pnl,
            'average_buy_price': avg_price,
            'execution_price': current_price
        }, msg, 200

    @staticmethod
    def get_user_holding(user_id: int, symbol: str) -> dict:
        """Returns user's holding details for a specific stock."""
        clean_symbol = InstrumentMappingService.normalize_symbol(symbol.strip().upper())
        holding = Holding.query.filter_by(user_id=user_id, symbol=clean_symbol).first()
        if not holding:
            return None
        return holding.to_dict()

    @staticmethod
    def get_user_holdings(user_id: int) -> list[dict]:
        """Returns all holdings belonging to the user with market valuation."""
        summary = PaperTradingService.get_portfolio_summary(user_id)
        return summary['holdings']

    @staticmethod
    def get_portfolio_summary(user_id: int) -> dict:
        """
        Calculates authoritative comprehensive portfolio analytics for a specific user:
        1. Virtual Cash: from user wallet
        2. Total Investment: sum of invested_amount (average_buy_price * quantity)
        3. Current Portfolio Value: sum of current_value (current_price * quantity)
        4. Total Portfolio Value: virtual_cash + current_portfolio_value
        5. Total Profit/Loss: current_portfolio_value - total_investment
        6. Total Profit/Loss %: (total_pnl / total_investment * 100)
        7. Holdings list with per-holding metrics:
           - Stock Symbol
           - Company Name
           - Quantity
           - Average Buy Price
           - Current Price
           - Invested Amount
           - Current Value
           - Profit/Loss
           - Profit/Loss %
        """
        wallet = WalletService.get_or_create_wallet(user_id)
        virtual_cash = round(wallet.virtual_cash, 2)

        holdings = Holding.query.filter_by(user_id=user_id).order_by(Holding.updated_at.desc()).all()

        total_investment = 0.0
        current_portfolio_value = 0.0
        holdings_list = []

        for h in holdings:
            quote = StockService.get_stock_quote(h.symbol)
            current_price = round(float(quote['current_price']), 2) if (quote and quote.get('current_price')) else round(h.average_buy_price, 2)
            company_name = (quote.get('name') if quote else None) or h.company_name or h.symbol

            qty = h.quantity
            avg_price = round(h.average_buy_price, 2)
            invested_amount = round(avg_price * qty, 2)
            current_val = round(current_price * qty, 2)
            pnl = round(current_val - invested_amount, 2)
            pnl_pct = round((pnl / invested_amount * 100), 2) if invested_amount > 0 else 0.0

            total_investment += invested_amount
            current_portfolio_value += current_val

            holdings_list.append({
                'id': h.id,
                'user_id': h.user_id,
                'symbol': h.symbol,
                'company_name': company_name,
                'exchange': h.exchange or 'NSE',
                'quantity': qty,
                'average_buy_price': avg_price,
                'formatted_average_buy_price': f"₹{avg_price:,.2f}",
                'current_price': current_price,
                'formatted_current_price': f"₹{current_price:,.2f}",
                'invested_amount': invested_amount,
                'total_invested': invested_amount,
                'formatted_invested_amount': f"₹{invested_amount:,.2f}",
                'current_value': current_val,
                'formatted_current_value': f"₹{current_val:,.2f}",
                'pnl': pnl,
                'formatted_pnl': f"{'+' if pnl >= 0 else ''}₹{pnl:,.2f}",
                'pnl_percent': pnl_pct,
                'formatted_pnl_percent': f"{'+' if pnl >= 0 else ''}{pnl_pct:.2f}%",
                'is_profit': pnl >= 0,
                'created_at': h.created_at.isoformat() if h.created_at else None,
                'updated_at': h.updated_at.isoformat() if h.updated_at else None
            })

        total_investment = round(total_investment, 2)
        current_portfolio_value = round(current_portfolio_value, 2)
        total_portfolio_value = round(virtual_cash + current_portfolio_value, 2)
        total_pnl = round(current_portfolio_value - total_investment, 2)
        total_pnl_pct = round((total_pnl / total_investment * 100), 2) if total_investment > 0 else 0.0

        return {
            'virtual_cash': virtual_cash,
            'formatted_virtual_cash': f"₹{virtual_cash:,.2f}",
            'total_investment': total_investment,
            'formatted_total_investment': f"₹{total_investment:,.2f}",
            'current_portfolio_value': current_portfolio_value,
            'formatted_current_portfolio_value': f"₹{current_portfolio_value:,.2f}",
            'total_portfolio_value': total_portfolio_value,
            'formatted_total_portfolio_value': f"₹{total_portfolio_value:,.2f}",
            'total_pnl': total_pnl,
            'formatted_total_pnl': f"{'+' if total_pnl >= 0 else ''}₹{total_pnl:,.2f}",
            'total_pnl_percent': total_pnl_pct,
            'formatted_total_pnl_percent': f"{'+' if total_pnl >= 0 else ''}{total_pnl_pct:.2f}%",
            'is_profit': total_pnl >= 0,
            'holdings_count': len(holdings_list),
            'holdings': holdings_list
        }

    @staticmethod
    def get_user_transactions(user_id: int, limit: int = None) -> list[dict]:
        """Returns transaction history for the user, with optional limit."""
        query = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.created_at.desc())
        if limit:
            query = query.limit(limit)
        txs = query.all()
        return [t.to_dict() for t in txs]
