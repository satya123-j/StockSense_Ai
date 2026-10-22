from flask import Blueprint, request
from backend.app.services.paper_trading_service import PaperTradingService
from backend.app.utils.helpers import success_response, error_response
from backend.app.utils.decorators import token_required

portfolio_bp = Blueprint('portfolio_api', __name__, url_prefix='/api/portfolio')

# ============================================================================
# 1. Paper Trading BUY Order
# ============================================================================
@portfolio_bp.route('/buy', methods=['POST'])
@token_required
def buy_stock(current_user):
    """
    Executes a simulated paper-trading BUY order for the authenticated user.
    Backend calculates actual costs from authoritative live quotes and user's private wallet.
    """
    data = request.get_json() or {}
    symbol = data.get('symbol')
    quantity = data.get('quantity')

    if not symbol:
        return error_response("Symbol is required.", status_code=400)

    if quantity is None:
        return error_response("Quantity is required.", status_code=400)

    result, message, status_code = PaperTradingService.buy_stock(
        user_id=current_user.id,
        symbol=symbol,
        quantity=quantity
    )

    if not result:
        return error_response(message=message, status_code=status_code)

    return success_response(data=result, message=message, status_code=status_code)


# ============================================================================
# 2. Paper Trading SELL Order
# ============================================================================
@portfolio_bp.route('/sell', methods=['POST'])
@token_required
def sell_stock(current_user):
    """
    Executes a simulated paper-trading SELL order for the authenticated user.
    Backend validates ownership, quantity owned, authoritative price, calculates sell value,
    realized profit/loss, updates virtual wallet, and closes/updates holding.
    """
    data = request.get_json() or {}
    symbol = data.get('symbol')
    quantity = data.get('quantity')

    if not symbol:
        return error_response("Symbol is required.", status_code=400)

    if quantity is None:
        return error_response("Quantity is required.", status_code=400)

    result, message, status_code = PaperTradingService.sell_stock(
        user_id=current_user.id,
        symbol=symbol,
        quantity=quantity
    )

    if not result:
        return error_response(message=message, status_code=status_code)

    return success_response(data=result, message=message, status_code=status_code)


# ============================================================================
# 3. Individual Holding & User Holdings Lookup
# ============================================================================
@portfolio_bp.route('/holding/<symbol>', methods=['GET'])
@token_required
def get_holding(current_user, symbol):
    """Retrieves current user's holding details for a specific stock."""
    holding = PaperTradingService.get_user_holding(current_user.id, symbol)
    return success_response(data=holding)


@portfolio_bp.route('/holdings', methods=['GET'])
@token_required
def get_holdings(current_user):
    """Retrieves all current user holdings."""
    holdings = PaperTradingService.get_user_holdings(current_user.id)
    return success_response(data=holdings)


# ============================================================================
# 4. Authoritative Portfolio Summary (Holdings, Invested, Market Value, P/L)
# ============================================================================
@portfolio_bp.route('/summary', methods=['GET'])
@token_required
def get_portfolio_summary(current_user):
    """
    Retrieves full authoritative portfolio analytics for the authenticated user:
    Virtual Cash, Total Investment, Current Portfolio Value, Total Portfolio Value,
    Total Profit/Loss, Total Profit/Loss %, and detailed holdings.
    """
    summary = PaperTradingService.get_portfolio_summary(current_user.id)
    return success_response(data=summary)


# ============================================================================
# 5. Transaction History
# ============================================================================
@portfolio_bp.route('/transactions', methods=['GET'])
@token_required
def get_transactions(current_user):
    """Retrieves transaction history for the authenticated user."""
    txs = PaperTradingService.get_user_transactions(current_user.id)
    return success_response(data=txs)
