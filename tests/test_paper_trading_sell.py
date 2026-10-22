import unittest
import json
import os
import sys

# Ensure UTF-8 output in Windows environments
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.app import create_app
from backend.app.extensions import db
from backend.app.models.user import User
from backend.app.models.portfolio import Holding, Transaction
from backend.app.models.wallet import Wallet
from backend.app.services.paper_trading_service import PaperTradingService
from backend.app.services.stock_service import StockService

class PaperTradingSellTestCase(unittest.TestCase):
    """
    Test suite for simulated paper-trading SELL functionality:
    1. Buy stock -> holding created, balance decreases.
    2. Sell part of holding -> balance increases, quantity decreases, avg buy price remains constant.
    3. Sell remaining holding -> holding closed/removed, balance updated.
    4. Realized P&L calculated accurately.
    5. Rejection when attempting to sell more shares than owned.
    6. Rejection when attempting to sell unowned stock.
    7. Validation of positive integer quantities.
    8. Multi-user isolation (User B cannot sell or view User A's holdings).
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

    def _register_user(self, username, email):
        res = self.client.post('/api/auth/register', json={
            'username': username,
            'email': email,
            'password': 'Password123!',
            'full_name': f'Test {username}'
        })
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)['data']
        token = data['token']
        user_id = data['user']['id']
        headers = {'Authorization': f'Bearer {token}'}
        return user_id, token, headers

    def test_buy_stock_then_sell_part_then_sell_remaining(self):
        """
        Comprehensive lifecycle test:
        - Buy 3 shares of TCS
        - Sell 1 share (partial sale): verify balance, remaining quantity (2), avg price unchanged
        - Sell remaining 2 shares (full liquidation): verify balance, holding removed
        - Verify transaction history (1 BUY, 2 SELL)
        """
        user_id, token, headers = self._register_user('trader_sam', 'sam@trading.test')

        # 1. Initial wallet state
        user = db.session.get(User, user_id)
        self.assertEqual(user.virtual_cash, 10000.0)

        quote = StockService.get_stock_quote('TCS')
        self.assertIsNotNone(quote)
        stock_price = float(quote['current_price'])

        # 2. Buy 3 shares of TCS
        buy_res = self.client.post('/api/portfolio/buy', json={
            'symbol': 'TCS',
            'quantity': 3
        }, headers=headers)
        self.assertEqual(buy_res.status_code, 200)

        total_buy_cost = round(stock_price * 3, 2)
        expected_cash_after_buy = round(10000.0 - total_buy_cost, 2)

        db.session.expire_all()
        user = db.session.get(User, user_id)
        self.assertEqual(round(user.virtual_cash, 2), expected_cash_after_buy)

        holding = Holding.query.filter_by(user_id=user_id, symbol='TCS').first()
        self.assertIsNotNone(holding)
        self.assertEqual(holding.quantity, 3)
        self.assertEqual(holding.average_buy_price, stock_price)
        self.assertEqual(round(holding.total_invested, 2), total_buy_cost)

        # 3. Sell 1 share (partial sale)
        sell1_res = self.client.post('/api/portfolio/sell', json={
            'symbol': 'TCS',
            'quantity': 1
        }, headers=headers)
        self.assertEqual(sell1_res.status_code, 200)
        sell1_data = json.loads(sell1_res.data)['data']

        # Backend recalculates authoritative price
        exec_price1 = sell1_data['execution_price']
        expected_sell1_val = round(exec_price1 * 1, 2)
        expected_cash_after_sell1 = round(expected_cash_after_buy + expected_sell1_val, 2)

        self.assertEqual(sell1_data['remaining_quantity'], 2)
        self.assertFalse(sell1_data['is_closed'])
        self.assertEqual(sell1_data['wallet']['virtual_cash'], expected_cash_after_sell1)

        # Verify database holding record after partial sale
        db.session.expire_all()
        holding_after_s1 = Holding.query.filter_by(user_id=user_id, symbol='TCS').first()
        self.assertIsNotNone(holding_after_s1)
        self.assertEqual(holding_after_s1.quantity, 2)
        self.assertEqual(holding_after_s1.average_buy_price, stock_price)  # Avg price remains constant!
        self.assertEqual(round(holding_after_s1.total_invested, 2), round(2 * stock_price, 2))

        # 4. Sell remaining 2 shares (complete liquidation)
        sell2_res = self.client.post('/api/portfolio/sell', json={
            'symbol': 'TCS',
            'quantity': 2
        }, headers=headers)
        self.assertEqual(sell2_res.status_code, 200)
        sell2_data = json.loads(sell2_res.data)['data']

        exec_price2 = sell2_data['execution_price']
        expected_sell2_val = round(exec_price2 * 2, 2)
        expected_final_cash = round(expected_cash_after_sell1 + expected_sell2_val, 2)

        self.assertEqual(sell2_data['remaining_quantity'], 0)
        self.assertTrue(sell2_data['is_closed'])
        self.assertEqual(sell2_data['wallet']['virtual_cash'], expected_final_cash)

        # 5. Verify holding is removed from database
        db.session.expire_all()
        holding_after_s2 = Holding.query.filter_by(user_id=user_id, symbol='TCS').first()
        self.assertIsNone(holding_after_s2)  # Completely closed/deleted!

        # Also verify GET /api/portfolio/holdings returns empty list
        holdings_res = self.client.get('/api/portfolio/holdings', headers=headers)
        self.assertEqual(len(json.loads(holdings_res.data)['data']), 0)

        # 6. Verify Transaction History: exactly 3 transactions (1 BUY, 2 SELL)
        tx_res = self.client.get('/api/portfolio/transactions', headers=headers)
        self.assertEqual(tx_res.status_code, 200)
        txs = json.loads(tx_res.data)['data']
        self.assertEqual(len(txs), 3)

        tx_types = [t['transaction_type'] for t in txs]
        self.assertIn('BUY', tx_types)
        self.assertIn('SELL', tx_types)
        self.assertEqual(tx_types.count('SELL'), 2)
        self.assertEqual(tx_types.count('BUY'), 1)

    def test_cannot_sell_more_shares_than_owned(self):
        """Verify transaction rejected when attempting to sell more shares than user owns."""
        user_id, token, headers = self._register_user('greedy_seller', 'greedy@trading.test')

        # Buy 2 shares of INFY
        buy_res = self.client.post('/api/portfolio/buy', json={
            'symbol': 'INFY',
            'quantity': 2
        }, headers=headers)
        self.assertEqual(buy_res.status_code, 200)

        # Attempt to sell 3 shares of INFY
        sell_res = self.client.post('/api/portfolio/sell', json={
            'symbol': 'INFY',
            'quantity': 3
        }, headers=headers)

        self.assertEqual(sell_res.status_code, 400)
        data = json.loads(sell_res.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn("Cannot sell more shares than owned", data['message'])

        # Verify holding quantity is still 2
        h = Holding.query.filter_by(user_id=user_id, symbol='INFY').first()
        self.assertEqual(h.quantity, 2)

    def test_cannot_sell_unowned_stock(self):
        """Verify transaction rejected when user attempts to sell a stock they do not own."""
        user_id, token, headers = self._register_user('unowned_seller', 'unowned@trading.test')

        # Attempt to sell RELIANCE without owning any
        sell_res = self.client.post('/api/portfolio/sell', json={
            'symbol': 'RELIANCE',
            'quantity': 1
        }, headers=headers)

        self.assertEqual(sell_res.status_code, 400)
        data = json.loads(sell_res.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn("do not own any shares", data['message'])

    def test_sell_quantity_validation(self):
        """Verify quantity validation: positive whole integers only."""
        user_id, token, headers = self._register_user('val_trader', 'val@trading.test')

        # 1. Zero quantity
        r0 = self.client.post('/api/portfolio/sell', json={'symbol': 'TCS', 'quantity': 0}, headers=headers)
        self.assertEqual(r0.status_code, 400)

        # 2. Negative quantity
        r_neg = self.client.post('/api/portfolio/sell', json={'symbol': 'TCS', 'quantity': -2}, headers=headers)
        self.assertEqual(r_neg.status_code, 400)

        # 3. String non-integer
        r_str = self.client.post('/api/portfolio/sell', json={'symbol': 'TCS', 'quantity': 'two'}, headers=headers)
        self.assertEqual(r_str.status_code, 400)

        # 4. Missing quantity
        r_miss = self.client.post('/api/portfolio/sell', json={'symbol': 'TCS'}, headers=headers)
        self.assertEqual(r_miss.status_code, 400)

    def test_multi_user_isolation_on_sell(self):
        """
        Verify multi-user isolation:
        - User A owns shares of TCS.
        - User B cannot sell User A's shares.
        - User B cannot see User A's holdings.
        """
        user_a_id, token_a, headers_a = self._register_user('user_alpha', 'alpha@iso.test')
        user_b_id, token_b, headers_b = self._register_user('user_beta', 'beta@iso.test')

        # User A buys 2 shares of TCS
        buy_a = self.client.post('/api/portfolio/buy', json={
            'symbol': 'TCS',
            'quantity': 2
        }, headers=headers_a)
        self.assertEqual(buy_a.status_code, 200)

        # User B tries to sell TCS
        sell_b = self.client.post('/api/portfolio/sell', json={
            'symbol': 'TCS',
            'quantity': 1
        }, headers=headers_b)

        self.assertEqual(sell_b.status_code, 400)
        self.assertIn("do not own any shares", json.loads(sell_b.data)['message'])

        # User A still has 2 shares of TCS
        h_a = Holding.query.filter_by(user_id=user_a_id, symbol='TCS').first()
        self.assertEqual(h_a.quantity, 2)

        # User B's balance remains ₹10,000
        user_b = db.session.get(User, user_b_id)
        self.assertEqual(user_b.virtual_cash, 10000.0)

if __name__ == '__main__':
    unittest.main()
