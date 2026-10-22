from flask import Blueprint, request
from backend.app.services.ml_service import MLService
from backend.app.services.instrument_mapping_service import InstrumentMappingService
from backend.app.utils.helpers import success_response, error_response, round_num

ml_bp = Blueprint('ml_api', __name__, url_prefix='/api/ml')


@ml_bp.route('/predict/<symbol>', methods=['GET'])
def predict_stock(symbol):
    """
    ML Prediction Endpoint:
    GET /api/ml/predict/<symbol>

    Fetches existing historical stock data for the requested Indian stock symbol,
    trains Linear Regression and Random Forest Regressor models on chronological time-series data,
    evaluates both models with MAE, RMSE, R², compares their performance,
    and returns next trading day predictions as JSON.
    """
    if not symbol:
        return error_response("Stock symbol is required.", status_code=400)

    clean_symbol = InstrumentMappingService.normalize_symbol(symbol)
    period = request.args.get('period', '1y')

    raw_result = MLService.predict(clean_symbol, period=period)

    if not raw_result or raw_result.get('status') == 'error':
        err_msg = (
            raw_result.get('message', f"Unable to generate predictions for '{clean_symbol}'.")
            if raw_result else "Prediction service failed."
        )
        status_code = 404 if "No historical candle" in err_msg else 400
        return error_response(err_msg, status_code=status_code)

    lr_data = raw_result['predictions']['linear_regression']
    rf_data = raw_result['predictions']['random_forest']
    comp = raw_result.get('comparison', {})
    data_summary = raw_result.get('data_summary', {})

    current_price = data_summary.get('current_close')

    # Selected / best model based on out-of-sample RMSE evaluation
    best_model_name = comp.get('best_model_by_rmse', 'Linear Regression')
    selected_model_data = rf_data if 'Random Forest' in best_model_name else lr_data

    predicted_price = selected_model_data.get('predicted_close')
    prediction_change = round_num(predicted_price - current_price, 2) if (predicted_price is not None and current_price is not None) else None
    prediction_change_pct = (
        round_num((prediction_change / current_price) * 100, 2)
        if (prediction_change is not None and current_price) else 0.0
    )

    # Core evaluation metrics for both models
    lr_metrics = {
        'mae': lr_data['metrics']['mae'],
        'rmse': lr_data['metrics']['rmse'],
        'r2': lr_data['metrics']['r2_score']
    }

    rf_metrics = {
        'mae': rf_data['metrics']['mae'],
        'rmse': rf_data['metrics']['rmse'],
        'r2': rf_data['metrics']['r2_score']
    }

    response_data = {
        'symbol': clean_symbol,
        'current_price': current_price,
        'predicted_price': predicted_price,
        'prediction_change': prediction_change,
        'prediction_change_percentage': prediction_change_pct,
        'selected_model': best_model_name,
        'linear_regression_metrics': lr_metrics,
        'random_forest_metrics': rf_metrics,
        'models': {
            'linear_regression': {
                'model_name': 'Linear Regression',
                'predicted_price': lr_data['predicted_close'],
                'prediction_change': lr_data['predicted_change'],
                'prediction_change_percentage': lr_data['predicted_change_percent'],
                'direction': lr_data.get('direction'),
                'metrics': lr_metrics,
                'coefficients': lr_data.get('coefficients')
            },
            'random_forest': {
                'model_name': 'Random Forest Regressor',
                'predicted_price': rf_data['predicted_close'],
                'prediction_change': rf_data['predicted_change'],
                'prediction_change_percentage': rf_data['predicted_change_percent'],
                'direction': rf_data.get('direction'),
                'metrics': rf_metrics,
                'feature_importances': rf_data.get('feature_importances')
            }
        },
        'comparison': {
            'selected_model': best_model_name,
            'best_by_rmse': comp.get('best_model_by_rmse'),
            'best_by_r2': comp.get('best_model_by_r2'),
            'rmse_difference': comp.get('rmse_delta')
        },
        'data_summary': {
            'total_historical_candles': data_summary.get('total_historical_candles'),
            'train_samples': data_summary.get('train_samples'),
            'test_samples': data_summary.get('test_samples'),
            'features_used': data_summary.get('features_used'),
            'latest_trading_date': data_summary.get('latest_candle_date')
        },
        'timestamp': raw_result.get('timestamp')
    }

    return success_response(data=response_data, message="Prediction generated successfully")
