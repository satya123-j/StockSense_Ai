import unittest
import os
import sys
import json

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.app import create_app


class ChatbotRoutesTestCase(unittest.TestCase):
    """Test suite for StockSense AI Chatbot REST API Routes."""

    def setUp(self):
        """Set up Flask test client with testing configuration."""
        self.app = create_app('testing')
        self.client = self.app.test_client()

        self.sample_context = {
            'symbol': 'RELIANCE',
            'company_name': 'Reliance Industries Ltd',
            'current_price': 2950.00,
            'rsi': 62.15,
            'macd': {'macd': 18.2, 'signal': 12.0, 'histogram': 6.2},
            'ma20': 2910.00,
            'ma50': 2860.00,
            'ml_prediction': {
                'predicted_price': 2985.00,
                'predicted_change': 35.00,
                'predicted_change_percentage': 1.19,
                'direction': 'UP',
                'selected_model': 'Random Forest Regressor'
            },
            'recommendation': {
                'verdict': 'BUY',
                'signal_score': 55,
                'normalized_score': 77.5,
                'explanation': 'Strong bullish technical alignment and positive ML forecast.'
            },
            'has_data': True
        }

    def test_chat_status_endpoint(self):
        """Test GET /api/chat/status returns operational details without exposing keys."""
        resp = self.client.get('/api/chat/status')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('active_provider', data['data'])
        self.assertIn('supported_queries', data['data'])
        # Never expose API keys
        self.assertNotIn('api_key', data['data'])
        self.assertNotIn('key', data['data'])

    def test_chat_endpoint_valid_request(self):
        """Test POST /api/chat with valid user_message and context."""
        payload = {
            'user_message': 'What is the current price?',
            'symbol': 'RELIANCE',
            'context': self.sample_context
        }
        resp = self.client.post(
            '/api/chat',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('2,950.00', data['data']['response'])
        self.assertIn('2,950.00', data['data']['answer'])
        self.assertEqual(data['data']['symbol'], 'RELIANCE')
        self.assertIn('suggested_questions', data['data'])
        # Never expose API keys
        self.assertNotIn('api_key', data['data'])
        self.assertNotIn('key', data['data'])

    def test_chat_endpoint_missing_user_message(self):
        """Test POST /api/chat fails gracefully with 400 when user_message is missing or empty."""
        payload = {
            'symbol': 'RELIANCE',
            'context': self.sample_context
        }
        resp = self.client.post(
            '/api/chat',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('user_message', data['message'])

    def test_chat_endpoint_missing_symbol(self):
        """Test POST /api/chat fails gracefully with 400 when symbol cannot be determined."""
        payload = {
            'user_message': 'What is the moving average?',
            'context': {}
        }
        resp = self.client.post(
            '/api/chat',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('symbol', data['message'].lower())

    def test_chat_endpoint_auto_extract_symbol_from_message(self):
        """Test POST /api/chat auto-extracts symbol when mentioned in user_message."""
        payload = {
            'user_message': 'What is the RSI of TCS right now?'
        }
        resp = self.client.post(
            '/api/chat',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['data']['symbol'], 'TCS')
        self.assertIn('TCS', data['data']['response'])

    def test_chat_endpoint_why_recommendation(self):
        """Test POST /api/chat asking why recommendation was generated."""
        payload = {
            'user_message': 'Why did the system generate this recommendation?',
            'symbol': 'RELIANCE',
            'context': self.sample_context
        }
        resp = self.client.post(
            '/api/chat',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('BUY', data['data']['response'])
        self.assertIn('+55 / 100', data['data']['response'])

    def test_chat_context_endpoint(self):
        """Test GET /api/chat/context/<symbol>."""
        resp = self.client.get('/api/chat/context/TCS')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['data']['symbol'], 'TCS')


if __name__ == '__main__':
    unittest.main()
