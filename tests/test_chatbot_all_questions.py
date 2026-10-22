import unittest
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.app.services.chatbot_service import ChatbotService


class ChatbotNaturalLanguageTestCase(unittest.TestCase):
    """
    Comprehensive verification for natural-language stock, technical,
    ML, recommendation, portfolio, and educational questions.
    """

    def setUp(self):
        self.sample_context = {
            'symbol': 'RELIANCE',
            'company_name': 'Reliance Industries Limited',
            'current_price': 2950.00,
            'change': 25.00,
            'change_percent': 0.85,
            'open': 2930.00,
            'previous_close': 2925.00,
            'day_high': 2965.00,
            'day_low': 2920.00,
            'volume': 4500000,
            'fifty_two_week_high': 3100.00,
            'fifty_two_week_low': 2220.00,
            'rsi': 62.50,
            'macd': {
                'macd': 18.50,
                'signal': 14.20,
                'histogram': 4.30
            },
            'ma20': 2910.00,
            'ma50': 2850.00,
            'ml_prediction': {
                'predicted_price': 2980.00,
                'predicted_change': 30.00,
                'predicted_change_percentage': 1.02,
                'direction': 'UP',
                'selected_model': 'Random Forest Regressor',
                'metrics': {'mae': 14.2, 'rmse': 18.1, 'r2': 0.89}
            },
            'recommendation': {
                'verdict': 'BUY',
                'signal_score': 50,
                'normalized_score': 75.0,
                'explanation': 'Bullish technical indicators and constructive ML projection.',
                'supporting_indicators': [
                    {'name': 'RSI (14)', 'score': 15, 'signal': 'BULLISH', 'interpretation': 'Constructive bullish momentum.'},
                    {'name': 'MACD', 'score': 20, 'signal': 'BULLISH', 'interpretation': 'MACD line above signal line.'},
                    {'name': 'Price vs MA20', 'score': 10, 'signal': 'BULLISH', 'interpretation': 'Price trading above MA20.'},
                    {'name': 'Price vs MA50', 'score': 10, 'signal': 'BULLISH', 'interpretation': 'Price trading above MA50.'}
                ]
            },
            'has_data': True
        }

        self.mock_user_portfolio = {
            'authenticated': True,
            'user_id': 1,
            'username': 'test_trader',
            'virtual_cash': 85000.00,
            'portfolio_summary': {
                'total_invested': 15000.00,
                'current_value': 16200.00,
                'total_pnl': 1200.00,
                'total_pnl_percent': 8.00
            },
            'holdings': [
                {
                    'symbol': 'TCS',
                    'quantity': 4,
                    'average_price': 3750.00,
                    'current_price': 4050.00,
                    'current_value': 16200.00,
                    'unrealized_pnl': 1200.00,
                    'unrealized_pnl_percent': 8.00
                }
            ],
            'recent_transactions': []
        }

    # =========================================================================
    # Step 6: Test the 9 specific questions sequentially
    # =========================================================================

    def test_the_nine_questions_distinct_and_sequential(self):
        """Verify that the 9 required test questions produce distinct, correct answers."""
        history = []
        questions = [
            ("Can I buy or hold this stock?", "Current AI Recommendation", "BUY"),
            ("What's the lowest price today?", "Lowest Price Today", "2,920.00"),
            ("What's the highest price today?", "Highest Price Today", "2,965.00"),
            ("What is the current price?", "Current Price", "2,950.00"),
            ("What is the RSI?", "What is RSI", "Relative Strength Index"),
            ("Why did the system recommend HOLD?", "Why StockSense AI Generated", "Scoring Framework"),
            ("What is the predicted next-day price?", "Machine Learning Price Forecast", "2,980.00"),
            ("What is MACD?", "What is MACD", "Moving Average Convergence Divergence"),
            ("What does that mean?", "Is MACD Bullish or Bearish", "MACD is Bullish")
        ]

        responses = []
        for q, expected_header, expected_content in questions:
            res = ChatbotService.generate_response(
                user_message=q,
                symbol="RELIANCE",
                context=self.sample_context,
                conversation_history=history
            )
            self.assertEqual(res['status'], 'success')
            text = res['data']['response']
            responses.append(text)
            self.assertIn(expected_header, text, f"Question '{q}' should contain '{expected_header}'")
            self.assertIn(expected_content, text, f"Question '{q}' should contain '{expected_content}'")
            history.append({'role': 'user', 'content': q})
            history.append({'role': 'assistant', 'content': text})

        # Ensure all 9 answers are different from each other
        unique_responses = set(responses)
        self.assertEqual(len(unique_responses), 9, "All 9 questions must produce distinct answers without repeating")

    # =========================================================================
    # Category A: Market Price Questions
    # =========================================================================

    def test_category_a_market_price_questions(self):
        # Open price
        res_open = ChatbotService.generate_response("What was the opening price today?", "RELIANCE", context=self.sample_context)
        self.assertIn("Opening Price", res_open['data']['response'])
        self.assertIn("2,930.00", res_open['data']['response'])

        # Previous close
        res_prev = ChatbotService.generate_response("What was yesterday's closing price?", "RELIANCE", context=self.sample_context)
        self.assertIn("Yesterday's Closing Price", res_prev['data']['response'])
        self.assertIn("2,925.00", res_prev['data']['response'])

        # Volume
        res_vol = ChatbotService.generate_response("What is the trading volume?", "RELIANCE", context=self.sample_context)
        self.assertIn("Trading Volume", res_vol['data']['response'])
        self.assertIn("4,500,000 shares", res_vol['data']['response'])

        # Price change
        res_chg = ChatbotService.generate_response("How much has the stock changed today?", "RELIANCE", context=self.sample_context)
        self.assertIn("Today's Price Movement", res_chg['data']['response'])
        self.assertIn("+25.00", res_chg['data']['response'])

        # Day low distinction from 52-week low
        res_low = ChatbotService.generate_response("What is the lowest price today?", "RELIANCE", context=self.sample_context)
        self.assertIn("2,920.00", res_low['data']['response'])
        self.assertIn("2,220.00", res_low['data']['response'])  # 52w low distinguished

    # =========================================================================
    # Category B: Technical Analysis Questions
    # =========================================================================

    def test_category_b_technical_questions(self):
        # RSI meaning
        res_rsi_mean = ChatbotService.generate_response("What does the current RSI indicate?", "RELIANCE", context=self.sample_context)
        self.assertIn("What does the RSI value mean", res_rsi_mean['data']['response'])
        self.assertIn("62.50", res_rsi_mean['data']['response'])

        # MACD bullish / bearish
        res_macd_trend = ChatbotService.generate_response("Is MACD bullish or bearish according to the available indicator data?", "RELIANCE", context=self.sample_context)
        self.assertIn("Is MACD Bullish or Bearish", res_macd_trend['data']['response'])
        self.assertIn("Bullish", res_macd_trend['data']['response'])

        # Price vs MA
        res_ma_vs = ChatbotService.generate_response("Is the current price above or below MA20 and MA50?", "RELIANCE", context=self.sample_context)
        self.assertIn("Current Price vs MA20 and MA50", res_ma_vs['data']['response'])
        self.assertIn("above both", res_ma_vs['data']['response'].lower())

    # =========================================================================
    # Category C: BUY / HOLD / SELL Questions
    # =========================================================================

    def test_category_c_recommendation_questions(self):
        # Supporting factors
        res_factors = ChatbotService.generate_response("What factors support the BUY recommendation?", "RELIANCE", context=self.sample_context)
        self.assertIn("Factors Supporting", res_factors['data']['response'])
        self.assertIn("RSI (14)", res_factors['data']['response'])

        # Selling analysis
        res_sell = ChatbotService.generate_response("What does the current analysis suggest about selling?", "RELIANCE", context=self.sample_context)
        self.assertIn("Selling Analysis", res_sell['data']['response'])

    # =========================================================================
    # Category D: ML Prediction Questions
    # =========================================================================

    def test_category_d_ml_questions(self):
        # Model selection
        res_model = ChatbotService.generate_response("Which ML model was selected?", "RELIANCE", context=self.sample_context)
        self.assertIn("Selected ML Model", res_model['data']['response'])
        self.assertIn("Random Forest Regressor", res_model['data']['response'])

        # MAE and RMSE
        res_metrics = ChatbotService.generate_response("What do MAE and RMSE mean?", "RELIANCE", context=self.sample_context)
        self.assertIn("What do MAE and RMSE Mean", res_metrics['data']['response'])
        self.assertIn("Mean Absolute Error", res_metrics['data']['response'])

        # Reliability
        res_rel = ChatbotService.generate_response("How reliable is the prediction?", "RELIANCE", context=self.sample_context)
        self.assertIn("Prediction Reliability", res_rel['data']['response'])
        self.assertIn("35% weight", res_rel['data']['response'])

    # =========================================================================
    # Category E: Portfolio and Paper Trading Questions
    # =========================================================================

    def test_category_e_portfolio_questions(self):
        # Virtual cash
        res_cash = ChatbotService.generate_response(
            "How much virtual cash do I have?",
            "RELIANCE",
            context=self.sample_context,
            user_portfolio=self.mock_user_portfolio
        )
        self.assertIn("85,000.00", res_cash['data']['response'])

        # Holdings
        res_holdings = ChatbotService.generate_response(
            "What stocks do I own?",
            "RELIANCE",
            context=self.sample_context,
            user_portfolio=self.mock_user_portfolio
        )
        self.assertIn("TCS", res_holdings['data']['response'])
        self.assertIn("4 shares", res_holdings['data']['response'])

        # PnL
        res_pnl = ChatbotService.generate_response(
            "How much profit or loss do I have?",
            "RELIANCE",
            context=self.sample_context,
            user_portfolio=self.mock_user_portfolio
        )
        self.assertIn("+1,200.00", res_pnl['data']['response'])

        # How many shares of TCS
        res_tcs = ChatbotService.generate_response(
            "How many shares of TCS do I own?",
            "RELIANCE",
            context=self.sample_context,
            user_portfolio=self.mock_user_portfolio
        )
        self.assertIn("4 shares", res_tcs['data']['response'])

        # Purchase cost calculation: "How much would buying two shares cost?"
        res_cost = ChatbotService.generate_response(
            "How much would buying two shares cost?",
            "RELIANCE",
            context=self.sample_context,
            user_portfolio=self.mock_user_portfolio
        )
        self.assertIn("5,900.00", res_cost['data']['response'])  # 2 * 2950
        self.assertIn("Paper Trading execution panel", res_cost['data']['response'])

        # Trade rejection reason
        res_rej = ChatbotService.generate_response(
            "Why was my BUY transaction rejected?",
            "RELIANCE",
            context=self.sample_context,
            user_portfolio=self.mock_user_portfolio
        )
        self.assertIn("Insufficient Virtual Cash", res_rej['data']['response'])

    # =========================================================================
    # Category F: Educational Questions
    # =========================================================================

    def test_category_f_educational_questions(self):
        # Stock market
        res_sm = ChatbotService.generate_response("What is a stock market?", "RELIANCE", context=self.sample_context)
        self.assertIn("What is the Stock Market?", res_sm['data']['response'])

        # Linear regression vs Random forest
        res_diff = ChatbotService.generate_response("What is the difference between Linear Regression and Random Forest?", "RELIANCE", context=self.sample_context)
        self.assertIn("Difference Between Linear Regression and Random Forest", res_diff['data']['response'])

        # Diversification
        res_div = ChatbotService.generate_response("What is diversification?", "RELIANCE", context=self.sample_context)
        self.assertIn("What is Portfolio Diversification?", res_div['data']['response'])

        # Investing vs Paper trading
        res_pt = ChatbotService.generate_response("What is the difference between investing and paper trading?", "RELIANCE", context=self.sample_context)
        self.assertIn("Difference Between Investing and Paper Trading", res_pt['data']['response'])

    # =========================================================================
    # Category G: Missing Data Handling
    # =========================================================================

    def test_missing_data_handling(self):
        sparse_ctx = {
            'symbol': 'TESTSTOCK',
            'company_name': 'Test Stock Ltd',
            'current_price': 100.0,
            'open': None,
            'day_low': None,
            'day_high': None,
            'rsi': None,
            'macd': {},
            'ma20': None,
            'ma50': None,
            'ml_prediction': None,
            'recommendation': None,
            'has_data': True
        }

        res_low = ChatbotService.generate_response("What is the lowest price today?", "TESTSTOCK", context=sparse_ctx)
        self.assertIn("cannot currently be retrieved", res_low['data']['response'])
        # Never substitute previous close or 52-week low
        self.assertNotIn("₹0.00", res_low['data']['response'])

        res_high = ChatbotService.generate_response("What is the highest price today?", "TESTSTOCK", context=sparse_ctx)
        self.assertIn("cannot currently be retrieved", res_high['data']['response'])


if __name__ == '__main__':
    unittest.main()
