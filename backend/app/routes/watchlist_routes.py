from flask import Blueprint, request
from backend.app.services.watchlist_service import WatchlistService
from backend.app.utils.helpers import success_response, error_response
from backend.app.utils.decorators import user_required

watchlist_bp = Blueprint('watchlist_api', __name__, url_prefix='/api/watchlist')

@watchlist_bp.route('', methods=['GET'])
@user_required
def get_watchlist(current_user):
    """Retrieve all watchlist items for the authenticated user."""
    items = WatchlistService.get_watchlist(current_user.id)
    return success_response(data=items)


@watchlist_bp.route('', methods=['POST'])
@user_required
def add_to_watchlist(current_user):
    """Add a new stock to authenticated user's watchlist."""
    data = request.get_json() or {}
    symbol = data.get('symbol')
    company_name = data.get('company_name')
    notes = data.get('notes')

    if not symbol:
        return error_response("Symbol is required.", status_code=400)

    result, message, status_code = WatchlistService.add_stock(
        user_id=current_user.id,
        symbol=symbol,
        company_name=company_name,
        notes=notes
    )

    if not result:
        return error_response(message=message, status_code=status_code)

    return success_response(data=result, message=message, status_code=status_code)


@watchlist_bp.route('/<path:identifier>', methods=['DELETE'])
@user_required
def remove_from_watchlist(current_user, identifier):
    """Remove a stock from watchlist by item ID or Symbol."""
    if identifier.startswith('symbol/'):
        sym = identifier.replace('symbol/', '', 1)
        success, message, status_code = WatchlistService.remove_stock(user_id=current_user.id, symbol=sym)
    elif identifier.isdigit():
        success, message, status_code = WatchlistService.remove_stock(user_id=current_user.id, item_id=int(identifier))
    else:
        success, message, status_code = WatchlistService.remove_stock(user_id=current_user.id, symbol=identifier)

    if not success:
        return error_response(message=message, status_code=status_code)

    return success_response(message=message, status_code=status_code)


@watchlist_bp.route('/check/<symbol>', methods=['GET'])
@user_required
def check_in_watchlist(current_user, symbol):
    """Check whether a stock is already saved in the user's watchlist."""
    is_saved = WatchlistService.check_is_in_watchlist(current_user.id, symbol)
    return success_response(data={'is_saved': is_saved})
