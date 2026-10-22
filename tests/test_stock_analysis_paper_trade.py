import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.app import create_app
from backend.app.extensions import db
from backend.app.models.user import User
from backend.app.models.portfolio import Holding, Transaction
from backend.app.models.wallet import Wallet
from backend.app.services.stock_service import StockService

class StockAnalysisPaperTradeTestCase(unittest.TestCase):
    """
    Test suite verifying the Paper Trade section integration within Stock Analysis:
    1. Stock Analysis HTML page contains the dedicated Paper Trade section with BUY & SELL controls.
    2. BUY features: Quantity input, current market price, total cost, available cash, confirm BUY.
    3. SELL features: Quantity input, current market price, owned quantity, total value, confirm SELL.
    4. Selected stock is bound to the Paper Trade section.
    5. Real current stock price from market-data system is used and backend computes authoritative transaction values.
    6. Virtual balance, portfolio, holdings, and transaction history update properly upon success.
    7. Clear error message on insufficient cash or overselling.
    8. Non-breakage: ML prediction, AI recommendation, technicals, and charts continue functioning properly.
    """

    def setUp(self):
        """Set up in-memory testing application and client."""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        """Clean up in-memory database after tests."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_stock_analysis_page_contains_paper_trade_section(self):
        """Verify the Stock Analysis template renders the in-page Paper Trade panel and required BUY/SELL elements."""
        res = self.client.get('/analysis/TCS')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        # 1. Section title & badge
        self.assertIn('Paper Trade', html)
        self.assertIn('inpage-paper-trade-panel', html)
        self.assertIn('pt-selected-symbol-badge', html)

        # 2. BUY Tab and elements
        self.assertIn('pt-tab-buy', html)
        self.assertIn('pt-buy-current-price', html)
        self.assertIn('pt-buy-available-cash', html)
        self.assertIn('pt-buy-qty-input', html)
        self.assertIn('pt-buy-total-cost', html)
        self.assertIn('Confirm BUY', html)
        self.assertIn('pt-buy-confirm-btn', html)

        # 3. SELL Tab and elements
        self.assertIn('pt-tab-sell', html)
        self.assertIn('pt-sell-current-price', html)
        self.assertIn('pt-sell-owned-qty', html)
        self.assertIn('pt-sell-qty-input', html)
        self.assertIn('pt-sell-total-value', html)
        self.assertIn('Confirm SELL', html)
        self.assertIn('pt-sell-confirm-btn', html)

        # 4. Error and success alert containers
        self.assertIn('pt-buy-error-alert', html)
        self.assertIn('pt-buy-success-alert', html)
        self.assertIn('pt-sell-error-alert', html)
        self.assertIn('pt-sell-success-alert', html)

    def test_paper_trade_buy_execution_and_state_updates(self):
        """Verify simulated BUY execution updates virtual balance, portfolio holding, and transaction history."""
        # 1. Register a test user
        reg_res = self.client.post('/api/auth/register', json={
            'username': 'trader_vikram',
            'email': 'vikram@stocksense.test',
            'password': 'password123',
            'full_name': 'Vikram Trader'
        })
        self.assertEqual(reg_res.status_code, 201)
        token = json.loads(reg_res.data)['data']['token']
        headers = {'Authorization': f'Bearer {token}'}

        # 2. Check initial virtual cash
        wallet_res = self.client.get('/api/user/wallet', headers=headers)
        self.assertEqual(wallet_res.status_code, 200)
        self.assertEqual(json.loads(wallet_res.data)['data']['virtual_cash'], 10000.0)

        # 3. Execute Paper Trade BUY for TCS (1 share)
        buy_res = self.client.post('/api/portfolio/buy', json={
            'symbol': 'TCS',
            'quantity': 1
        }, headers=headers)

        self.assertEqual(buy_res.status_code, 200)
        buy_data = json.loads(buy_res.data)
        self.assertEqual(buy_data['status'], 'success')

        # Backend calculated values
        tx = buy_data['data']['transaction']
        self.assertEqual(tx['symbol'], 'TCS')
        self.assertEqual(tx['transaction_type'], 'BUY')
        self.assertEqual(tx['quantity'], 1)
        exec_price = tx['price']
        total_cost = tx['total_amount']
        self.assertAlmostEqual(total_cost, exec_price * 1, places=2)

        # Verify virtual balance decreased
        new_balance = buy_data['data']['wallet']['virtual_cash']
        self.assertAlmostEqual(new_balance, 10000.0 - total_cost, places=2)

        # Verify holding exists for user
        holding_res = self.client.get('/api/portfolio/holding/TCS', headers=headers)
        self.assertEqual(holding_res.status_code, 200)
        holding_data = json.loads(holding_res.data)['data']
        self.assertIsNotNone(holding_data)
        self.assertEqual(holding_data['quantity'], 1)
        self.assertAlmostEqual(holding_data['average_buy_price'], exec_price, places=2)

        # Verify transaction appears in user transaction history
        history_res = self.client.get('/api/portfolio/transactions', headers=headers)
        self.assertEqual(history_res.status_code, 200)
        history_list = json.loads(history_res.data)['data']
        self.assertIsInstance(history_list, list)
        self.assertEqual(len(history_list), 1)
        self.assertEqual(history_list[0]['symbol'], 'TCS')
        self.assertEqual(history_list[0]['transaction_type'], 'BUY')

    def test_paper_trade_sell_execution_and_pnl_updates(self):
        """Verify simulated SELL execution updates cash, reduces holdings, and logs SELL transaction."""
        # 1. Register test user
        reg_res = self.client.post('/api/auth/register', json={
            'username': 'trader_kavita',
            'email': 'kavita@stocksense.test',
            'password': 'password123',
            'full_name': 'Kavita Trader'
        })
        token = json.loads(reg_res.data)['data']['token']
        headers = {'Authorization': f'Bearer {token}'}

        # 2. Buy 2 shares of INFOSYS
        buy_res = self.client.post('/api/portfolio/buy', json={
            'symbol': 'INFY',
            'quantity': 2
        }, headers=headers)
        self.assertEqual(buy_res.status_code, 200)
        post_buy_cash = json.loads(buy_res.data)['data']['wallet']['virtual_cash']

        # 3. Sell 1 share of INFOSYS
        sell_res = self.client.post('/api/portfolio/sell', json={
            'symbol': 'INFY',
            'quantity': 1
        }, headers=headers)
        self.assertEqual(sell_res.status_code, 200)
        sell_data = json.loads(sell_res.data)
        self.assertEqual(sell_data['status'], 'success')

        tx = sell_data['data']['transaction']
        self.assertEqual(tx['transaction_type'], 'SELL')
        self.assertEqual(tx['quantity'], 1)
        sell_price = tx['price']
        sell_amount = tx['total_amount']
        self.assertAlmostEqual(sell_amount, sell_price * 1, places=2)

        # Verify virtual balance increased by sell amount
        new_cash = sell_data['data']['wallet']['virtual_cash']
        self.assertAlmostEqual(new_cash, post_buy_cash + sell_amount, places=2)

        # Verify remaining holding is 1 share
        holding_res = self.client.get('/api/portfolio/holding/INFY', headers=headers)
        holding_data = json.loads(holding_res.data)['data']
        self.assertIsNotNone(holding_data)
        self.assertEqual(holding_data['quantity'], 1)

    def test_insufficient_funds_rejection(self):
        """Verify simulated BUY rejects orders exceeding virtual cash balance."""
        reg_res = self.client.post('/api/auth/register', json={
            'username': 'trader_budget',
            'email': 'budget@stocksense.test',
            'password': 'password123',
            'full_name': 'Budget Trader'
        })
        token = json.loads(reg_res.data)['data']['token']
        headers = {'Authorization': f'Bearer {token}'}

        # Attempt to buy 100 shares of MRF or expensive stock (far exceeding ₹10,000)
        res = self.client.post('/api/portfolio/buy', json={
            'symbol': 'TCS',
            'quantity': 10000 # Way over 10k budget
        }, headers=headers)

        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Insufficient', data['message'])

        # Verify balance remains unchanged
        wallet_res = self.client.get('/api/user/wallet', headers=headers)
        self.assertEqual(json.loads(wallet_res.data)['data']['virtual_cash'], 10000.0)

    def test_overselling_rejection(self):
        """Verify simulated SELL rejects attempts to sell more shares than owned."""
        reg_res = self.client.post('/api/auth/register', json={
            'username': 'trader_short',
            'email': 'short@stocksense.test',
            'password': 'password123',
            'full_name': 'Short Trader'
        })
        token = json.loads(reg_res.data)['data']['token']
        headers = {'Authorization': f'Bearer {token}'}

        # Attempt to sell stock not owned
        res = self.client.post('/api/portfolio/sell', json={
            'symbol': 'RELIANCE',
            'quantity': 1
        }, headers=headers)

        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('do not own', data['message'].lower())

    def test_existing_analysis_features_unbroken(self):
        """Verify ML Prediction, AI Recommendation, and Stock History endpoints remain functional and untouched."""
        # 1. Historical candles
        hist_res = self.client.get('/api/stocks/TCS/history?range=1m')
        self.assertEqual(hist_res.status_code, 200)
        hist_data = json.loads(hist_res.data)
        self.assertIn('points', hist_data['data'])

        # 2. ML Prediction
        ml_res = self.client.get('/api/ml/predict/TCS')
        self.assertEqual(ml_res.status_code, 200)
        ml_data = json.loads(ml_res.data)
        self.assertIn('predicted_price', ml_data['data'])

        # 3. AI Recommendation
        rec_res = self.client.get('/api/recommendation/TCS')
        self.assertEqual(rec_res.status_code, 200)
        rec_data = json.loads(rec_res.data)
        self.assertIn('recommendation', rec_data['data'])
        self.assertIn(rec_data['data']['recommendation'], ['BUY', 'HOLD', 'SELL'])

if __name__ == '__main__':
    unittest.main()
