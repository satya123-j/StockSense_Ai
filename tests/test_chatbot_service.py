import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.app.services.chatbot_service import ChatbotService


class ChatbotServiceTestCase(unittest.TestCase):
    """Test suite for StockSense AI Chatbot Service."""

    def setUp(self):
        """Prepare sample stock context for tests."""
        self.sample_context = {
            'symbol': 'TCS',
            'company_name': 'Tata Consultancy Services Ltd',
            'current_price': 3850.50,
            'currency': 'INR',
            'change': 25.30,
            'change_percent': 0.66,
            'previous_close': 3825.20,
            'day_high': 3870.00,
            'day_low': 3830.00,
            'rsi': 58.42,
            'macd': {
                'macd': 12.40,
                'signal': 8.10,
                'histogram': 4.30
            },
            'ma20': 3820.10,
            'ma50': 3780.00,
            'ml_prediction': {
                'predicted_price': 3892.00,
                'predicted_change': 41.50,
                'predicted_change_percentage': 1.08,
                'direction': 'UP',
                'selected_model': 'Random Forest Regressor',
                'metrics': {'mae': 15.2, 'rmse': 18.4, 'r2': 0.88}
            },
            'recommendation': {
                'verdict': 'BUY',
                'signal_score': 45,
                'normalized_score': 72.5,
                'explanation': 'Positive technical indicators and ML forward projections outweigh downside risks.',
                'supporting_indicators': [
                    {'name': 'RSI (14)', 'score': 15, 'signal': 'BULLISH', 'interpretation': 'Positive upward momentum (58.42).'},
                    {'name': 'MACD (12, 26, 9)', 'score': 20, 'signal': 'BULLISH', 'interpretation': 'Bullish momentum (MACD > Signal).'},
                    {'name': 'Price vs MA20', 'score': 10, 'signal': 'BULLISH', 'interpretation': 'Price trading above MA20.'},
                    {'name': 'Price vs MA50', 'score': 10, 'signal': 'BULLISH', 'interpretation': 'Price trading above MA50.'},
                    {'name': 'MA Trend Alignment', 'score': 5, 'signal': 'BULLISH', 'interpretation': 'Bullish MA20 > MA50 alignment.'},
                    {'name': 'ML Next-Day Forecast', 'score': 25, 'signal': 'BULLISH', 'interpretation': 'Moderate Bullish ML forecast.'}
                ]
            },
            'has_data': True
        }

    def test_normalize_context_complete(self):
        """Test normalization of a fully populated context dictionary."""
        normalized = ChatbotService.normalize_context(self.sample_context, 'TCS')
        self.assertEqual(normalized['symbol'], 'TCS')
        self.assertEqual(normalized['current_price'], 3850.50)
        self.assertEqual(normalized['rsi'], 58.42)
        self.assertEqual(normalized['macd']['macd'], 12.40)
        self.assertEqual(normalized['ma20'], 3820.10)
        self.assertEqual(normalized['ma50'], 3780.00)
        self.assertEqual(normalized['ml_prediction']['predicted_price'], 3892.00)
        self.assertEqual(normalized['recommendation']['verdict'], 'BUY')
        self.assertTrue(normalized['has_data'])

    def test_normalize_context_empty_no_hallucination(self):
        """Test that an empty context does not invent or hallucinate data."""
        normalized = ChatbotService.normalize_context({}, 'INFY')
        self.assertEqual(normalized['symbol'], 'INFY')
        self.assertIsNone(normalized['current_price'])
        self.assertIsNone(normalized['rsi'])
        self.assertIsNone(normalized['macd']['macd'])
        self.assertIsNone(normalized['ma20'])
        self.assertIsNone(normalized['ma50'])
        self.assertIsNone(normalized['ml_prediction'])
        self.assertIsNone(normalized['recommendation'])
        self.assertFalse(normalized['has_data'])

    def test_answer_current_price(self):
        """Test answering: What is the current price?"""
        res = ChatbotService.generate_response(
            user_message="What is the current price?",
            symbol="TCS",
            context=self.sample_context
        )
        self.assertEqual(res['status'], 'success')
        text = res['data']['response']
        self.assertIn("3,850.50", text)
        self.assertIn("TCS", text)

    def test_answer_what_is_rsi(self):
        """Test answering: What is RSI?"""
        res = ChatbotService.generate_response(
            user_message="What is RSI?",
            symbol="TCS",
            context=self.sample_context
        )
        self.assertEqual(res['status'], 'success')
        text = res['data']['response']
        self.assertIn("Relative Strength Index", text)
        self.assertIn("Overbought", text)
        self.assertIn("Oversold", text)
        self.assertIn("58.42", text)

    def test_answer_what_does_rsi_value_mean(self):
        """Test answering: What does the RSI value mean?"""
        res = ChatbotService.generate_response(
            user_message="What does the RSI value mean?",
            symbol="TCS",
            context=self.sample_context
        )
        self.assertEqual(res['status'], 'success')
        text = res['data']['response']
        self.assertIn("58.42", text)
        self.assertIn("Bullish Momentum", text)

    def test_answer_what_is_macd(self):
        """Test answering: What is MACD?"""
        res = ChatbotService.generate_response(
            user_message="What is MACD?",
            symbol="TCS",
            context=self.sample_context
        )
        self.assertEqual(res['status'], 'success')
        text = res['data']['response']
        self.assertIn("Moving Average Convergence Divergence", text)
        self.assertIn("Signal Line", text)
        self.assertIn("Histogram", text)
        self.assertIn("12.40", text)

    def test_answer_ma20_and_ma50(self):
        """Test answering: What is the MA20 and MA50?"""
        res = ChatbotService.generate_response(
            user_message="What is the MA20 and MA50?",
            symbol="TCS",
            context=self.sample_context
        )
        self.assertEqual(res['status'], 'success')
        text = res['data']['response']
        self.assertIn("MA20", text)
        self.assertIn("MA50", text)
        self.assertIn("3,820.10", text)
        self.assertIn("3,780.00", text)

    def test_answer_ml_predicted_price(self):
        """Test answering: What is the ML predicted price?"""
        res = ChatbotService.generate_response(
            user_message="What is the ML predicted price?",
            symbol="TCS",
            context=self.sample_context
        )
        self.assertEqual(res['status'], 'success')
        text = res['data']['response']
        self.assertIn("3,892.00", text)
        self.assertIn("Random Forest Regressor", text)
        self.assertIn("+1.08%", text)

    def test_answer_current_recommendation(self):
        """Test answering: What is the current AI recommendation?"""
        res = ChatbotService.generate_response(
            user_message="What is the current AI recommendation?",
            symbol="TCS",
            context=self.sample_context
        )
        self.assertEqual(res['status'], 'success')
        text = res['data']['response']
        self.assertIn("BUY", text)
        self.assertIn("+45 / 100", text)

    def test_answer_why_recommendation(self):
        """Test answering: Why did the system generate this recommendation?"""
        res = ChatbotService.generate_response(
            user_message="Why did the system generate this recommendation?",
            symbol="TCS",
            context=self.sample_context
        )
        self.assertEqual(res['status'], 'success')
        text = res['data']['response']
        self.assertIn("Scoring Framework", text)
        self.assertIn("RSI Momentum", text)
        self.assertIn("MACD", text)
        self.assertIn("Moving Average", text)
        self.assertIn("Machine Learning", text)
        self.assertIn("+45 / 100", text)

    def test_missing_data_transparency(self):
        """Test that missing indicators are handled transparently without making up values."""
        empty_ctx = {
            'symbol': 'XYZ_STOCK',
            'current_price': None,
            'rsi': None,
            'macd': {},
            'ma20': None,
            'ma50': None,
            'ml_prediction': None,
            'recommendation': None,
            'has_data': True
        }
        res_price = ChatbotService.generate_response(
            user_message="What is the current price?",
            symbol="XYZ_STOCK",
            context=empty_ctx
        )
        self.assertIn("currently unavailable", res_price['data']['response'].lower())

        res_ml = ChatbotService.generate_response(
            user_message="What is the ML predicted price?",
            symbol="XYZ_STOCK",
            context=empty_ctx
        )
        self.assertIn("currently unavailable", res_ml['data']['response'].lower())

    @patch('backend.app.services.chatbot_service.requests.post')
    def test_external_gemini_api_integration(self, mock_post):
        """Test that external Gemini API is invoked when GEMINI_API_KEY is configured."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candidates': [
                {
                    'content': {
                        'parts': [{'text': 'Gemini generated response for TCS.'}]
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake_test_key_123', 'CHATBOT_PROVIDER': 'gemini'}):
            res = ChatbotService.generate_response(
                user_message="Tell me about TCS",
                symbol="TCS",
                context=self.sample_context
            )
            self.assertEqual(res['status'], 'success')
            self.assertEqual(res['data']['provider'], 'gemini')
            self.assertIn('Gemini generated response', res['data']['response'])

    @patch('backend.app.services.chatbot_service.requests.post')
    def test_external_api_failure_fallback_to_domain_engine(self, mock_post):
        """Test that if external AI API fails or times out, it gracefully falls back to domain engine."""
        mock_post.side_effect = Exception("API connection timed out")

        with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake_test_key_123', 'CHATBOT_PROVIDER': 'gemini'}):
            res = ChatbotService.generate_response(
                user_message="What is the current price?",
                symbol="TCS",
                context=self.sample_context
            )
            self.assertEqual(res['status'], 'success')
            self.assertEqual(res['data']['provider'], 'domain_engine')
            self.assertIn("3,850.50", res['data']['response'])


if __name__ == '__main__':
    unittest.main()
