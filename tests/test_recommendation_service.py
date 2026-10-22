import unittest
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.recommendation_service import RecommendationService


class RecommendationServiceTestCase(unittest.TestCase):
    """Test suite for StockSense AI RecommendationService."""

    def test_rsi_evaluation_tiers(self):
        """Test RSI scoring logic across oversold, neutral, and overbought tiers."""
        # Oversold (<= 30) -> +20 pts (BULLISH)
        res_os = RecommendationService.evaluate_rsi(25.0)
        self.assertEqual(res_os['signal'], 'BULLISH')
        self.assertEqual(res_os['score'], 20)

        # Subdued (30 < RSI < 45) -> -5 pts (BEARISH)
        res_sub = RecommendationService.evaluate_rsi(35.0)
        self.assertEqual(res_sub['signal'], 'BEARISH')
        self.assertEqual(res_sub['score'], -5)

        # Neutral (45 <= RSI <= 55) -> 0 pts (NEUTRAL)
        res_neu = RecommendationService.evaluate_rsi(50.0)
        self.assertEqual(res_neu['signal'], 'NEUTRAL')
        self.assertEqual(res_neu['score'], 0)

        # Bullish momentum (55 < RSI < 70) -> +15 pts (BULLISH)
        res_bull = RecommendationService.evaluate_rsi(62.0)
        self.assertEqual(res_bull['signal'], 'BULLISH')
        self.assertEqual(res_bull['score'], 15)

        # Overbought (>= 70) -> -15 pts (BEARISH)
        res_ob = RecommendationService.evaluate_rsi(75.0)
        self.assertEqual(res_ob['signal'], 'BEARISH')
        self.assertEqual(res_ob['score'], -15)

        # None / missing
        res_none = RecommendationService.evaluate_rsi(None)
        self.assertEqual(res_none['signal'], 'NEUTRAL')
        self.assertEqual(res_none['score'], 0)

    def test_macd_evaluation_tiers(self):
        """Test MACD scoring logic for crossovers and histogram momentum."""
        # Bullish crossover with positive histogram -> +20 pts
        res_pos = RecommendationService.evaluate_macd(macd=5.0, signal_line=3.0, histogram=2.0)
        self.assertEqual(res_pos['signal'], 'BULLISH')
        self.assertEqual(res_pos['score'], 20)

        # Bullish crossover with narrowing histogram -> +10 pts
        res_narrow = RecommendationService.evaluate_macd(macd=5.0, signal_line=4.0, histogram=-0.5)
        self.assertEqual(res_narrow['signal'], 'BULLISH')
        self.assertEqual(res_narrow['score'], 10)

        # Bearish crossover with negative histogram -> -20 pts
        res_bear = RecommendationService.evaluate_macd(macd=-5.0, signal_line=-2.0, histogram=-3.0)
        self.assertEqual(res_bear['signal'], 'BEARISH')
        self.assertEqual(res_bear['score'], -20)

    def test_moving_averages_evaluation(self):
        """Test MA20 and MA50 price relationship and alignment scoring."""
        # Price above MA20 and MA50, with MA20 > MA50 (Golden alignment)
        # Price=105, MA20=100 (+10), MA50=95 (+10), Alignment=+5 => Total 25 pts
        res = RecommendationService.evaluate_moving_averages(price=105.0, ma20=100.0, ma50=95.0)
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0]['score'], 10)  # Price vs MA20
        self.assertEqual(res[1]['score'], 10)  # Price vs MA50
        self.assertEqual(res[2]['score'], 5)   # MA20 vs MA50

        # Price below both MAs with MA20 < MA50 (Death alignment)
        # Price=85, MA20=95 (-10), MA50=100 (-10), Alignment=-5 => Total -25 pts
        res_bear = RecommendationService.evaluate_moving_averages(price=85.0, ma20=95.0, ma50=100.0)
        self.assertEqual(res_bear[0]['score'], -10)
        self.assertEqual(res_bear[1]['score'], -10)
        self.assertEqual(res_bear[2]['score'], -5)

    def test_ml_prediction_evaluation(self):
        """Test ML forecast scoring across percentage movement tiers."""
        # Strong gain (+2.5%) -> +35 pts
        res_strong = RecommendationService.evaluate_ml_prediction(
            predicted_price=102.5, current_price=100.0, predicted_change_pct=2.5
        )
        self.assertEqual(res_strong['signal'], 'BULLISH')
        self.assertEqual(res_strong['score'], 35)

        # Moderate gain (+1.0%) -> +25 pts
        res_mod = RecommendationService.evaluate_ml_prediction(
            predicted_price=101.0, current_price=100.0, predicted_change_pct=1.0
        )
        self.assertEqual(res_mod['score'], 25)

        # Flat / Neutral (0.05%) -> 0 pts
        res_flat = RecommendationService.evaluate_ml_prediction(
            predicted_price=100.05, current_price=100.0, predicted_change_pct=0.05
        )
        self.assertEqual(res_flat['signal'], 'NEUTRAL')
        self.assertEqual(res_flat['score'], 0)

        # Moderate decline (-1.2%) -> -25 pts
        res_dec = RecommendationService.evaluate_ml_prediction(
            predicted_price=98.8, current_price=100.0, predicted_change_pct=-1.2
        )
        self.assertEqual(res_dec['signal'], 'BEARISH')
        self.assertEqual(res_dec['score'], -25)

    def test_recommendation_decision_boundaries(self):
        """Verify BUY, HOLD, SELL trigger boundaries."""
        # Buy boundary: score >= 20
        # Hold boundary: -20 < score < 20
        # Sell boundary: score <= -20

        # High bullish synthetic indicators
        tech_bull = {
            'latest': {
                'rsi': 60.0,           # +15
                'macd': 2.0,            # +20
                'macd_signal': 1.0,
                'macd_histogram': 1.0,
                'ma_20': 95.0,          # +10 (price=100)
                'ma_50': 90.0,          # +10
                'close': 100.0          # +5 alignment -> total tech = 60
            }
        }
        ml_bull = {
            'status': 'success',
            'data_summary': {'current_close': 100.0},
            'predictions': {
                'linear_regression': {
                    'predicted_close': 102.0,
                    'predicted_change': 2.0,
                    'predicted_change_percent': 2.0,
                    'direction': 'UP',
                    'metrics': {'mae': 1.0, 'rmse': 1.5, 'r2_score': 0.85}
                }
            },
            'comparison': {'best_model_by_rmse': 'Linear Regression'}
        }
        res_bull = RecommendationService.get_recommendation('TEST_BUY', tech_data=tech_bull, ml_data=ml_bull, use_cache=False)
        self.assertEqual(res_bull['recommendation'], 'BUY')
        self.assertGreaterEqual(res_bull['signal_score'], 20)

        # High bearish synthetic indicators
        tech_bear = {
            'latest': {
                'rsi': 35.0,           # -5
                'macd': -5.0,           # -20
                'macd_signal': -2.0,
                'macd_histogram': -3.0,
                'ma_20': 105.0,         # -10 (price=100)
                'ma_50': 110.0,         # -10
                'close': 100.0          # -5 alignment -> total tech = -50
            }
        }
        ml_bear = {
            'status': 'success',
            'data_summary': {'current_close': 100.0},
            'predictions': {
                'linear_regression': {
                    'predicted_close': 98.0,
                    'predicted_change': -2.0,
                    'predicted_change_percent': -2.0,
                    'direction': 'DOWN',
                    'metrics': {'mae': 1.0, 'rmse': 1.5, 'r2_score': 0.85}
                }
            },
            'comparison': {'best_model_by_rmse': 'Linear Regression'}
        }
        res_bear = RecommendationService.get_recommendation('TEST_SELL', tech_data=tech_bear, ml_data=ml_bear, use_cache=False)
        self.assertEqual(res_bear['recommendation'], 'SELL')
        self.assertLessEqual(res_bear['signal_score'], -20)

    def test_live_recommendation_structure(self):
        """Verify get_recommendation returns all required fields on real project stock data."""
        res = RecommendationService.get_recommendation('TCS')
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['symbol'], 'TCS')
        self.assertIn(res['recommendation'], ['BUY', 'HOLD', 'SELL'])
        self.assertIsInstance(res['signal_score'], int)
        self.assertIsInstance(res['explanation'], str)
        self.assertGreater(len(res['explanation']), 20)
        self.assertIsInstance(res['supporting_indicators'], list)
        self.assertEqual(len(res['supporting_indicators']), 6)
        self.assertIn('ml_prediction_information', res)
        self.assertIn('predicted_price', res['ml_prediction_information'])
        self.assertIn('predicted_change_percentage', res['ml_prediction_information'])

    def test_api_recommendation_endpoint(self):
        """Verify GET /api/recommendation/<symbol> returns 200 with all required fields."""
        from backend.app import create_app
        import json
        app = create_app('testing')
        client = app.test_client()

        for sym in ['RELIANCE', 'TCS', 'HDFCBANK']:
            res = client.get(f'/api/recommendation/{sym}')
            self.assertEqual(res.status_code, 200, f"Failed for {sym}")
            payload = json.loads(res.data)
            self.assertEqual(payload['status'], 'success')
            d = payload['data']

            # Required fields
            self.assertEqual(d['symbol'], sym)
            self.assertIn('current_price', d)
            self.assertIn('rsi', d)
            self.assertIn('macd', d)
            self.assertIn('ma20', d)
            self.assertIn('ma50', d)
            self.assertIn('predicted_price', d)
            self.assertIn('prediction_change_percentage', d)
            self.assertIn(d['recommendation'], ['BUY', 'HOLD', 'SELL'])
            self.assertIsInstance(d['signal_score'], int)
            self.assertIsInstance(d['explanation'], str)

    def test_api_recommendation_invalid_symbol(self):
        """Verify GET /api/recommendation/<symbol> gracefully returns 404 for non-existent stock."""
        from backend.app import create_app
        import json
        app = create_app('testing')
        client = app.test_client()

        res = client.get('/api/recommendation/INVALID_NONEXISTENT_XYZ_999')
        self.assertEqual(res.status_code, 404)
        payload = json.loads(res.data)
        self.assertEqual(payload['status'], 'error')


if __name__ == '__main__':
    unittest.main()
