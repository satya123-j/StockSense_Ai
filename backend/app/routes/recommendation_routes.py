from flask import Blueprint, request
from backend.app.services.recommendation_service import RecommendationService
from backend.app.services.technical_analysis_service import TechnicalAnalysisService
from backend.app.services.ml_service import MLService
from backend.app.services.instrument_mapping_service import InstrumentMappingService
from backend.app.utils.helpers import success_response, error_response

recommendation_bp = Blueprint('recommendation_api', __name__, url_prefix='/api')


@recommendation_bp.route('/recommendation/<symbol>', methods=['GET'])
@recommendation_bp.route('/stocks/<symbol>/recommendation', methods=['GET'])
def get_recommendation(symbol):
    """
    AI Stock Recommendation API Endpoint:
    GET /api/recommendation/<symbol>

    Fetches current stock quote, technical indicators (RSI, MACD, MA20, MA50),
    and ML prediction forecasts, then evaluates them into a composite recommendation
    (BUY, HOLD, SELL) with transparent scoring, supporting indicators, and explanation.
    """
    if not symbol:
        return error_response("Stock symbol is required.", status_code=400)

    clean_symbol = InstrumentMappingService.normalize_symbol(symbol)

    # 1. Fetch technical indicators (RSI, MACD, MA20, MA50, Close)
    tech_data = TechnicalAnalysisService.calculate_indicators(clean_symbol, period='1y')

    # 2. Fetch ML prediction (Predicted Price, Predicted Change %, Selected Model)
    ml_data = MLService.predict(clean_symbol, period='1y')

    # 3. Generate recommendation from actual project data
    rec = RecommendationService.get_recommendation(
        clean_symbol,
        tech_data=tech_data,
        ml_data=ml_data
    )

    current_price = rec.get('current_stock_price')
    raw_ind = rec.get('raw_indicators', {})
    ml_info = rec.get('ml_prediction_information', {})

    # Gracefully handle missing / non-existent security
    if current_price is None and (not tech_data or tech_data.get('error')):
        return error_response(
            f"Security symbol '{clean_symbol}' not found on NSE/BSE or has no active market data.",
            status_code=404
        )

    response_payload = {
        'symbol': clean_symbol,
        'current_price': current_price,
        'rsi': raw_ind.get('rsi'),
        'macd': raw_ind.get('macd'),
        'ma20': raw_ind.get('ma20'),
        'ma50': raw_ind.get('ma50'),
        'predicted_price': ml_info.get('predicted_price'),
        'prediction_change_percent': ml_info.get('predicted_change_percentage'),
        'prediction_change_percentage': ml_info.get('predicted_change_percentage'),
        'recommendation': rec.get('recommendation'),
        'signal_score': rec.get('signal_score'),
        'normalized_score': rec.get('normalized_score'),
        'explanation': rec.get('explanation'),
        'supporting_indicators': rec.get('supporting_indicators', []),
        'ml_prediction_information': ml_info,
        'timestamp': rec.get('timestamp')
    }

    return success_response(data=response_payload)
