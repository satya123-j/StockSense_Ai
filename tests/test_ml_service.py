import unittest
import json
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.app import create_app
from backend.app.extensions import db
from backend.app.services.ml_service import MLService


def _generate_synthetic_stock_data(n_days=120, start_price=100.0, seed=42):
    """Generates synthetic daily OHLCV stock DataFrame for testing."""
    np.random.seed(seed)
    base_date = datetime(2023, 1, 1)
    
    dates = []
    current_date = base_date
    while len(dates) < n_days:
        if current_date.weekday() < 5:  # Monday to Friday
            dates.append(current_date)
        current_date += timedelta(days=1)
        
    prices = [start_price]
    for _ in range(n_days - 1):
        ret = np.random.normal(0.001, 0.02)
        prices.append(prices[-1] * (1 + ret))
        
    data = []
    for i, (dt, close_p) in enumerate(zip(dates, prices)):
        spread = close_p * 0.01
        open_p = close_p + np.random.uniform(-spread, spread)
        high_p = max(open_p, close_p) + abs(np.random.uniform(0, spread))
        low_p = min(open_p, close_p) - abs(np.random.uniform(0, spread))
        volume = int(np.random.uniform(100000, 1000000))
        
        data.append({
            'date': dt.strftime('%Y-%m-%d'),
            'open': round(open_p, 2),
            'high': round(high_p, 2),
            'low': round(low_p, 2),
            'close': round(close_p, 2),
            'volume': volume
        })
        
    return pd.DataFrame(data)


class MLServiceTestCase(unittest.TestCase):
    """Test suite for StockSense AI Machine Learning Service."""

    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_feature_preparation_columns(self):
        """Verify all 8 required features (OHLCV, Prev Close, MA20, MA50) and Target are prepared."""
        df = _generate_synthetic_stock_data(n_days=100)
        prepared_df, features = MLService.prepare_features(df)

        expected_features = ['Open', 'High', 'Low', 'Close', 'Volume', 'Previous Close', 'MA20', 'MA50']
        for feat in expected_features:
            self.assertIn(feat, features, f"Missing feature: {feat}")
            self.assertIn(feat, prepared_df.columns, f"Column {feat} not in prepared DataFrame")

        self.assertIn('Target', prepared_df.columns)
        
        # Verify Previous Close calculation
        self.assertTrue(pd.isna(prepared_df['Previous Close'].iloc[0]))
        self.assertAlmostEqual(prepared_df['Previous Close'].iloc[1], prepared_df['Close'].iloc[0])
        
        # Verify MA20 is NaN for first 19 rows, populated from 20th row (index 19)
        self.assertTrue(prepared_df['MA20'].iloc[:19].isna().all())
        self.assertFalse(pd.isna(prepared_df['MA20'].iloc[19]))
        
        # Verify MA50 is NaN for first 49 rows, populated from 50th row (index 49)
        self.assertTrue(prepared_df['MA50'].iloc[:49].isna().all())
        self.assertFalse(pd.isna(prepared_df['MA50'].iloc[49]))

    def test_chronological_split_no_shuffling(self):
        """Verify data is split strictly chronologically without any random shuffling."""
        df = _generate_synthetic_stock_data(n_days=100)
        prepared_df, features = MLService.prepare_features(df)
        splits = MLService.split_time_series_data(prepared_df, features, test_size=0.2)

        train_df = splits['train_df']
        test_df = splits['test_df']

        # Ensure train and test sets are not empty
        self.assertGreater(len(train_df), 0)
        self.assertGreater(len(test_df), 0)

        # Ensure dates in train set strictly precede dates in test set
        max_train_date = train_df['Date'].max()
        min_test_date = test_df['Date'].min()
        self.assertLess(max_train_date, min_test_date, "Train set dates must be strictly earlier than test set dates")

        # Verify no overlap between train and test
        overlap = set(train_df.index).intersection(set(test_df.index))
        self.assertEqual(len(overlap), 0, "No indices should overlap between train and test splits")

    def test_linear_regression_and_random_forest_training(self):
        """Verify both Linear Regression and Random Forest Regressor train, evaluate, and forecast."""
        df = _generate_synthetic_stock_data(n_days=100)
        result = MLService.predict_from_dataframe(df, symbol="TEST_STOCK", test_size=0.2)

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['symbol'], 'TEST_STOCK')
        
        predictions = result['predictions']
        self.assertIn('linear_regression', predictions)
        self.assertIn('random_forest', predictions)
        self.assertIn('ensemble', predictions)

        # Validate Linear Regression
        lr = predictions['linear_regression']
        self.assertIn('predicted_close', lr)
        self.assertIn('direction', lr)
        self.assertIn(lr['direction'], ['UP', 'DOWN'])
        self.assertIn('coefficients', lr)
        self.assertIn('metrics', lr)
        self.assertIn('rmse', lr['metrics'])
        self.assertIn('mae', lr['metrics'])
        self.assertIn('r2_score', lr['metrics'])

        # Validate Random Forest
        rf = predictions['random_forest']
        self.assertIn('predicted_close', rf)
        self.assertIn('direction', rf)
        self.assertIn(rf['direction'], ['UP', 'DOWN'])
        self.assertIn('feature_importances', rf)
        self.assertIn('metrics', rf)
        self.assertIn('rmse', rf['metrics'])
        self.assertIn('mae', rf['metrics'])
        self.assertIn('r2_score', rf['metrics'])

        # Validate Ensemble
        ens = predictions['ensemble']
        self.assertIn('predicted_close', ens)
        self.assertIn('direction', ens)

        # Validate Comparison & Recent series
        self.assertIn('comparison', result)
        self.assertIn('best_model_by_rmse', result['comparison'])
        self.assertIn('recent_test_series', result)
        self.assertGreater(len(result['recent_test_series']), 0)

    def test_insufficient_data_error_handling(self):
        """Verify clean error reporting when historical candles are insufficient for MA50."""
        short_df = _generate_synthetic_stock_data(n_days=30)
        result = MLService.predict_from_dataframe(short_df, symbol="SHORT_STOCK")
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('Insufficient historical data', result['message'])

    def test_api_predict_endpoint(self):
        """Verify Flask API route GET /api/stocks/<symbol>/predict returns 200 with predictions."""
        res = self.client.get('/api/stocks/TCS/predict')
        self.assertEqual(res.status_code, 200)
        payload = json.loads(res.data)
        
        self.assertEqual(payload['status'], 'success')
        data = payload['data']
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['symbol'], 'TCS')

    def test_get_api_ml_predict_symbols(self):
        """Verify GET /api/ml/predict/<symbol> for RELIANCE, TCS, HDFCBANK with all required keys."""
        for symbol in ['RELIANCE', 'TCS', 'HDFCBANK']:
            res = self.client.get(f'/api/ml/predict/{symbol}')
            self.assertEqual(res.status_code, 200, f"Failed for {symbol}")
            payload = json.loads(res.data)
            
            self.assertEqual(payload['status'], 'success')
            data = payload['data']
            
            # Verify all required fields
            self.assertEqual(data['symbol'], symbol)
            self.assertIn('current_price', data)
            self.assertIn('predicted_price', data)
            self.assertIn('prediction_change', data)
            self.assertIn('prediction_change_percentage', data)
            self.assertIn('selected_model', data)
            
            # Verify Linear Regression metrics
            lr_metrics = data['linear_regression_metrics']
            self.assertIn('mae', lr_metrics)
            self.assertIn('rmse', lr_metrics)
            self.assertIn('r2', lr_metrics)
            
            # Verify Random Forest metrics
            rf_metrics = data['random_forest_metrics']
            self.assertIn('mae', rf_metrics)
            self.assertIn('rmse', rf_metrics)
            self.assertIn('r2', rf_metrics)
            
            # Verify models structure
            self.assertIn('linear_regression', data['models'])
            self.assertIn('random_forest', data['models'])


if __name__ == '__main__':
    unittest.main()
