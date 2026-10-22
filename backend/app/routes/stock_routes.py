from flask import Blueprint, request, session
from backend.app.services.stock_service import StockService
from backend.app.services.technical_analysis_service import TechnicalAnalysisService
from backend.app.services.ml_service import MLService
from backend.app.models.stock import RecentView
from backend.app.models.user import User
from backend.app.extensions import db
from backend.app.utils.helpers import success_response, error_response
import jwt
from flask import current_app

stock_bp = Blueprint('stock_api', __name__, url_prefix='/api')

# ============================================================================
# 1. User Context Helper
# ============================================================================
def _try_get_user():
    """Helper to detect logged-in user if token or session is present."""
    auth_header = request.headers.get('Authorization')
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            try:
                payload = jwt.decode(parts[1], current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
                return db.session.get(User, payload.get('user_id'))
            except Exception:
                pass
    if 'user_id' in session:
        return db.session.get(User, session['user_id'])
    return None


# ============================================================================
# 2. Stock Search & Real-Time Quotes
# ============================================================================
@stock_bp.route('/stocks/search', methods=['GET'])
def search():
    """Search Indian stocks by symbol or company name."""
    query = request.args.get('q', '').strip()
    limit = int(request.args.get('limit', 10))
    results = StockService.search_stocks(query, limit=limit)
    return success_response(data=results)


@stock_bp.route('/stocks/<symbol>', methods=['GET'])
@stock_bp.route('/stocks/<symbol>/quote', methods=['GET'])
@stock_bp.route('/stocks/<symbol>/overview', methods=['GET'])
def get_stock_overview(symbol):
    """Fetches comprehensive quote and company overview."""
    if not symbol:
        return error_response("Symbol is required.", status_code=400)

    data = StockService.get_stock_quote(symbol)
    if not data:
        return error_response(f"Stock data for {symbol} could not be retrieved.", status_code=404)

    # Track recent view if user is logged in
    user = _try_get_user()
    if user and data.get('symbol'):
        try:
            sym = data['symbol']
            c_name = data.get('name', sym)
            existing = RecentView.query.filter_by(user_id=user.id, symbol=sym).first()
            if existing:
                existing.company_name = c_name
                existing.viewed_at = db.func.now()
            else:
                new_view = RecentView(user_id=user.id, symbol=sym, company_name=c_name)
                db.session.add(new_view)
            db.session.commit()
        except Exception:
            db.session.rollback()

    return success_response(data=data)


# ============================================================================
# 3. Market Session Status & Broad Indices
# ============================================================================
@stock_bp.route('/market/status', methods=['GET'])
def get_market_status():
    """Fetches Indian market trading hours status and Upstox API configuration state."""
    from backend.app.services.upstox_service import UpstoxService
    status_data = UpstoxService.get_market_session_status()
    return success_response(data=status_data)


@stock_bp.route('/market/indices', methods=['GET'])
def get_market_indices():
    """Fetches top Indian market indices (NIFTY 50, SENSEX, BANK NIFTY)."""
    indices = StockService.get_market_indices()
    return success_response(data=indices)


# ============================================================================
# 4. Historical Chart Data
# ============================================================================
@stock_bp.route('/stocks/<symbol>/history', methods=['GET'])
def get_stock_history(symbol):
    """Fetches historical price data for charts."""
    range_period = request.args.get('range', '1mo')
    interval = request.args.get('interval', '1d')
    
    data = StockService.get_stock_history(symbol, range_period=range_period, interval=interval)
    return success_response(data=data)


# ============================================================================
# 5. Technical Analysis (RSI, MACD, Moving Averages)
# ============================================================================
@stock_bp.route('/stocks/<symbol>/technical-analysis', methods=['GET'])
@stock_bp.route('/stocks/<symbol>/technicals', methods=['GET'])
def get_stock_technicals(symbol):
    """Computes technical analysis indicators: SMA, EMA, RSI, MACD, Bollinger Bands."""
    period = request.args.get('period', '1y')
    data = TechnicalAnalysisService.calculate_indicators(symbol, period=period)
    return success_response(data=data)


# ============================================================================
# 6. Machine Learning Price Prediction
# ============================================================================
@stock_bp.route('/stocks/<symbol>/predict', methods=['GET'])
@stock_bp.route('/stocks/<symbol>/prediction', methods=['GET'])
def get_stock_prediction(symbol):
    """Computes ML price predictions using Linear Regression and Random Forest."""
    period = request.args.get('period', '1y')
    data = MLService.predict(symbol, period=period)
    if not data or data.get('status') == 'error':
        return error_response(data.get('message', f"Prediction failed for {symbol}"), status_code=400)
    return success_response(data=data)

