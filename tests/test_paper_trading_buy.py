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
from backend.app.services.paper_trading_service import PaperTradingService
from backend.app.services.stock_service import StockService

class PaperTradingBuyTestCase(unittest.TestCase):
    """
    Test suite for simulated paper-trading BUY functionality:
    1. New user starts with ₹10,000.
    2. Buy a stock -> balance decreases, holding is created, transaction recorded.
    3. Weighted average price updates correctly on subsequent buys.
    4. Insufficient funds rejection.
    5. Invalid input validation (quantity <= 0, non-integers, empty symbol).
    6. Multi-user isolation: User B cannot see User A's holdings.
    7. Persistence across session reloads.
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

    def test_new_user_starts_with_10000(self):
        """Verify newly registered user automatically starts with ₹10,000 virtual balance."""
        res = self.client.post('/api/auth/register', json={
            'username': 'buyer_alice',
            'email': 'alice@paper.test',
            'password': 'password123',
            'full_name': 'Alice Buyer'
        })
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)['data']

        self.assertEqual(data['user']['virtual_cash'], 10000.0)
        user = User.query.filter_by(username='buyer_alice').first()
        self.assertEqual(user.virtual_cash, 10000.0)
        self.assertEqual(len(user.holdings), 0)

    def test_buy_stock_decreases_balance_and_creates_holding(self):
        """
        Verify buying a stock:
        - Decreases virtual balance by actual total_cost (current_price * quantity)
        - Creates holding record with quantity, average_buy_price, total_invested
        - Creates BUY transaction record
        - Persists across database reloads
        """
        # 1. Register user
        reg_res = self.client.post('/api/auth/register', json={
            'username': 'buyer_bob',
            'email': 'bob@paper.test',
            'password': 'password123',
            'full_name': 'Bob Buyer'
        })
        user_token = json.loads(reg_res.data)['data']['token']
        user_id = json.loads(reg_res.data)['data']['user']['id']
        headers = {'Authorization': f'Bearer {user_token}'}

        # Check initial balance
        initial_balance = 10000.0

        # 2. Get authoritative stock price for TCS
        quote = StockService.get_stock_quote('TCS')
        self.assertIsNotNone(quote)
        self.assertIn('current_price', quote)
        stock_price = float(quote['current_price'])
        self.assertGreater(stock_price, 0)

        buy_qty = 2
        expected_cost = round(stock_price * buy_qty, 2)
        expected_balance = round(initial_balance - expected_cost, 2)

        # 3. Execute BUY via API
        buy_res = self.client.post('/api/portfolio/buy', json={
            'symbol': 'TCS',
            'quantity': buy_qty
        }, headers=headers)

        self.assertEqual(buy_res.status_code, 200)
        data = json.loads(buy_res.data)['data']

        # Verify returned data
        self.assertEqual(data['wallet']['virtual_cash'], expected_balance)
        self.assertEqual(data['holding']['symbol'], 'TCS')
        self.assertEqual(data['holding']['quantity'], buy_qty)
        self.assertEqual(data['holding']['average_buy_price'], stock_price)
        self.assertEqual(data['holding']['total_invested'], expected_cost)
        self.assertEqual(data['transaction']['transaction_type'], 'BUY')
        self.assertEqual(data['transaction']['quantity'], buy_qty)
        self.assertEqual(data['transaction']['total_amount'], expected_cost)

        # 4. Verify Database Persistence
        db.session.expire_all()
        refreshed_user = db.session.get(User, user_id)
        self.assertEqual(refreshed_user.virtual_cash, expected_balance)
        self.assertEqual(len(refreshed_user.holdings), 1)

        holding = refreshed_user.holdings[0]
        self.assertEqual(holding.symbol, 'TCS')
        self.assertEqual(holding.quantity, buy_qty)
        self.assertEqual(holding.average_buy_price, stock_price)
        self.assertEqual(holding.total_invested, expected_cost)

        # 5. Query holdings via GET /api/portfolio/holdings
        holdings_res = self.client.get('/api/portfolio/holdings', headers=headers)
        self.assertEqual(holdings_res.status_code, 200)
        holdings_data = json.loads(holdings_res.data)['data']
        self.assertEqual(len(holdings_data), 1)
        self.assertEqual(holdings_data[0]['symbol'], 'TCS')
        self.assertEqual(holdings_data[0]['quantity'], buy_qty)

    def test_weighted_average_buy_price_on_multiple_buys(self):
        """
        Verify that buying additional shares of the same stock
        correctly updates the weighted average buy price.
        """
        reg_res = self.client.post('/api/auth/register', json={
            'username': 'trader_dave',
            'email': 'dave@paper.test',
            'password': 'password123',
            'full_name': 'Dave Trader'
        })
        user_id = json.loads(reg_res.data)['data']['user']['id']

        # First buy: 1 share of RELIANCE @ 2500
        # Directly invoke service to test exact math
        w1, _, code1 = PaperTradingService.buy_stock(user_id, 'RELIANCE', 1)
        self.assertEqual(code1, 200)
        h1 = w1['holding']
        p1 = h1['average_buy_price']

        # Second buy: 1 more share
        w2, _, code2 = PaperTradingService.buy_stock(user_id, 'RELIANCE', 1)
        self.assertEqual(code2, 200)
        h2 = w2['holding']

        # Total quantity should now be 2
        self.assertEqual(h2['quantity'], 2)
        # Total invested should be 2 * average
        self.assertAlmostEqual(h2['total_invested'], 2 * h2['average_buy_price'], places=1)

    def test_insufficient_virtual_funds_rejected(self):
        """Verify transaction is rejected when user does not have enough virtual cash."""
        reg_res = self.client.post('/api/auth/register', json={
            'username': 'poor_trader',
            'email': 'poor@paper.test',
            'password': 'password123'
        })
        user_token = json.loads(reg_res.data)['data']['token']
        headers = {'Authorization': f'Bearer {user_token}'}

        # Try to buy 10,000 shares of TCS (far exceeds ₹10,000 cash)
        res = self.client.post('/api/portfolio/buy', json={
            'symbol': 'TCS',
            'quantity': 10000
        }, headers=headers)

        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn("Insufficient virtual funds", data['message'])

        # Balance remains ₹10,000
        user = User.query.filter_by(username='poor_trader').first()
        self.assertEqual(user.virtual_cash, 10000.0)
        self.assertEqual(len(user.holdings), 0)

    def test_invalid_input_validation(self):
        """Verify quantity must be positive integer and symbol must be provided."""
        reg_res = self.client.post('/api/auth/register', json={
            'username': 'validator_user',
            'email': 'validator@paper.test',
            'password': 'password123'
        })
        token = json.loads(reg_res.data)['data']['token']
        headers = {'Authorization': f'Bearer {token}'}

        # 1. Zero quantity
        r0 = self.client.post('/api/portfolio/buy', json={'symbol': 'INFY', 'quantity': 0}, headers=headers)
        self.assertEqual(r0.status_code, 400)

        # 2. Negative quantity
        r_neg = self.client.post('/api/portfolio/buy', json={'symbol': 'INFY', 'quantity': -5}, headers=headers)
        self.assertEqual(r_neg.status_code, 400)

        # 3. String non-integer quantity
        r_str = self.client.post('/api/portfolio/buy', json={'symbol': 'INFY', 'quantity': 'abc'}, headers=headers)
        self.assertEqual(r_str.status_code, 400)

        # 4. Missing symbol
        r_sym = self.client.post('/api/portfolio/buy', json={'quantity': 1}, headers=headers)
        self.assertEqual(r_sym.status_code, 400)

    def test_multi_user_portfolio_isolation(self):
        """
        CRITICAL TEST:
        User A buys a stock.
        User B logs in and CANNOT see User A's holdings.
        User B's balance remains ₹10,000.
        """
        # 1. Register User A and User B
        res_a = self.client.post('/api/auth/register', json={
            'username': 'investor_alpha',
            'email': 'alpha@iso.test',
            'password': 'password123'
        })
        token_a = json.loads(res_a.data)['data']['token']

        res_b = self.client.post('/api/auth/register', json={
            'username': 'investor_beta',
            'email': 'beta@iso.test',
            'password': 'password123'
        })
        token_b = json.loads(res_b.data)['data']['token']

        headers_a = {'Authorization': f'Bearer {token_a}'}
        headers_b = {'Authorization': f'Bearer {token_b}'}

        # 2. User A buys 1 share of INFY
        buy_a = self.client.post('/api/portfolio/buy', json={
            'symbol': 'INFY',
            'quantity': 1
        }, headers=headers_a)
        self.assertEqual(buy_a.status_code, 200)

        # 3. Verify User A has 1 holding and decreased balance
        holdings_a = self.client.get('/api/portfolio/holdings', headers=headers_a)
        data_a = json.loads(holdings_a.data)['data']
        self.assertEqual(len(data_a), 1)
        self.assertEqual(data_a[0]['symbol'], 'INFY')

        user_a = User.query.filter_by(username='investor_alpha').first()
        self.assertLess(user_a.virtual_cash, 10000.0)

        # 4. Verify User B CANNOT see User A's holding
        holdings_b = self.client.get('/api/portfolio/holdings', headers=headers_b)
        data_b = json.loads(holdings_b.data)['data']
        self.assertEqual(len(data_b), 0)  # Empty! Cannot see User A's holdings

        # User B specific holding check for INFY
        single_h_b = self.client.get('/api/portfolio/holding/INFY', headers=headers_b)
        self.assertIsNone(json.loads(single_h_b.data)['data'])

        # User B's balance is untouched at ₹10,000
        user_b = User.query.filter_by(username='investor_beta').first()
        self.assertEqual(user_b.virtual_cash, 10000.0)

if __name__ == '__main__':
    unittest.main()
