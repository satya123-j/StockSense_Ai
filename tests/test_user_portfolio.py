import unittest
import json
import os
import sys

# Ensure UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.app import create_app
from backend.app.extensions import db
from backend.app.models.user import User
from backend.app.models.portfolio import Holding, Transaction
from backend.app.services.paper_trading_service import PaperTradingService
from backend.app.services.stock_service import StockService

class UserPortfolioTestCase(unittest.TestCase):
    """
    Test suite for the User Portfolio feature:
    1. Initial state for new user: ₹10,000 cash, 0 investment, 0 holdings.
    2. Comprehensive portfolio analytics after buying stocks:
       - Virtual Cash
       - Total Investment = sum(average_buy_price * quantity)
       - Current Portfolio Value = sum(current_price * quantity)
       - Total Portfolio Value = virtual_cash + current_portfolio_value
       - Total Profit/Loss = current_portfolio_value - total_investment
       - Total Profit/Loss % = (total_pnl / total_investment * 100)
    3. Per-holding breakdown metrics:
       - symbol, company_name, quantity, average_buy_price, current_price,
       - invested_amount, current_value, pnl, pnl_percent
    4. Complete multi-user data isolation:
       - User A and User B have separate portfolios, holdings, balances, transactions.
       - Neither can see or access the other's portfolio data.
    5. Route protection:
       - Unauthenticated access to /portfolio redirects to /login.
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

    def _register(self, username, email):
        res = self.client.post('/api/auth/register', json={
            'username': username,
            'email': email,
            'password': 'Password123!',
            'full_name': f'Investor {username}'
        })
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)['data']
        token = data['token']
        user_id = data['user']['id']
        headers = {'Authorization': f'Bearer {token}'}
        return user_id, token, headers

    def test_new_user_empty_portfolio_summary(self):
        """Verify initial portfolio summary for a newly registered user."""
        user_id, token, headers = self._register('new_investor', 'new@invest.test')

        res = self.client.get('/api/portfolio/summary', headers=headers)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)['data']

        # Verify all 6 core metrics for new user
        self.assertEqual(data['virtual_cash'], 10000.0)
        self.assertEqual(data['total_investment'], 0.0)
        self.assertEqual(data['current_portfolio_value'], 0.0)
        self.assertEqual(data['total_portfolio_value'], 10000.0)
        self.assertEqual(data['total_pnl'], 0.0)
        self.assertEqual(data['total_pnl_percent'], 0.0)
        self.assertEqual(data['holdings_count'], 0)
        self.assertEqual(len(data['holdings']), 0)

    def test_portfolio_summary_after_stock_purchases(self):
        """
        Verify portfolio calculations after purchasing multiple stocks:
        - Buys 2 shares of TCS
        - Buys 1 share of INFY
        - Verifies exact math for Total Investment, Current Portfolio Value,
          Total Portfolio Value, and per-holding fields.
        """
        user_id, token, headers = self._register('active_portfolio_user', 'active@invest.test')

        # Buy 2 shares of TCS
        b1 = self.client.post('/api/portfolio/buy', json={'symbol': 'TCS', 'quantity': 2}, headers=headers)
        self.assertEqual(b1.status_code, 200)

        # Buy 1 share of INFY
        b2 = self.client.post('/api/portfolio/buy', json={'symbol': 'INFY', 'quantity': 1}, headers=headers)
        self.assertEqual(b2.status_code, 200)

        # Fetch authoritative portfolio summary
        res = self.client.get('/api/portfolio/summary', headers=headers)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)['data']

        self.assertEqual(data['holdings_count'], 2)
        holdings = data['holdings']

        # Get authoritative quotes to check against
        quote_tcs = StockService.get_stock_quote('TCS')
        quote_infy = StockService.get_stock_quote('INFY')
        price_tcs = round(float(quote_tcs['current_price']), 2)
        price_infy = round(float(quote_infy['current_price']), 2)

        expected_tcs_invested = round(price_tcs * 2, 2)
        expected_infy_invested = round(price_infy * 1, 2)
        expected_total_investment = round(expected_tcs_invested + expected_infy_invested, 2)
        expected_cash = round(10000.0 - expected_total_investment, 2)

        # Verify 6 core portfolio metrics
        self.assertEqual(data['virtual_cash'], expected_cash)
        self.assertEqual(data['total_investment'], expected_total_investment)
        self.assertAlmostEqual(data['current_portfolio_value'], expected_total_investment, places=1)
        self.assertAlmostEqual(data['total_portfolio_value'], round(expected_cash + data['current_portfolio_value'], 2), places=1)

        # Check holding fields for every owned stock
        symbols = [h['symbol'] for h in holdings]
        self.assertIn('TCS', symbols)
        self.assertIn('INFY', symbols)

        for h in holdings:
            self.assertIn('symbol', h)
            self.assertIn('company_name', h)
            self.assertIn('quantity', h)
            self.assertIn('average_buy_price', h)
            self.assertIn('current_price', h)
            self.assertIn('invested_amount', h)
            self.assertIn('current_value', h)
            self.assertIn('pnl', h)
            self.assertIn('pnl_percent', h)

            # Mathematical validation
            self.assertEqual(h['invested_amount'], round(h['average_buy_price'] * h['quantity'], 2))
            self.assertEqual(h['current_value'], round(h['current_price'] * h['quantity'], 2))
            self.assertEqual(h['pnl'], round(h['current_value'] - h['invested_amount'], 2))

    def test_complete_data_isolation_between_two_users(self):
        """
        CRITICAL TEST:
        User A registers and buys 2 shares of TCS.
        User B registers and buys 1 share of RELIANCE.

        Verify:
        - User A sees ONLY TCS, User A's balance, and User A's transactions.
        - User B sees ONLY RELIANCE, User B's balance, and User B's transactions.
        - User A never sees User B's holdings, balance, or transactions.
        - User B never sees User A's holdings, balance, or transactions.
        """
        user_a_id, token_a, headers_a = self._register('user_alpha', 'alpha@port.test')
        user_b_id, token_b, headers_b = self._register('user_beta', 'beta@port.test')

        # User A buys 2 shares of TCS
        res_buy_a = self.client.post('/api/portfolio/buy', json={'symbol': 'TCS', 'quantity': 2}, headers=headers_a)
        self.assertEqual(res_buy_a.status_code, 200)

        # User B buys 1 share of RELIANCE
        res_buy_b = self.client.post('/api/portfolio/buy', json={'symbol': 'RELIANCE', 'quantity': 1}, headers=headers_b)
        self.assertEqual(res_buy_b.status_code, 200)

        # 1. Query User A portfolio summary
        summary_a_res = self.client.get('/api/portfolio/summary', headers=headers_a)
        self.assertEqual(summary_a_res.status_code, 200)
        data_a = json.loads(summary_a_res.data)['data']

        # User A checks
        self.assertEqual(data_a['holdings_count'], 1)
        self.assertEqual(data_a['holdings'][0]['symbol'], 'TCS')
        self.assertEqual(data_a['holdings'][0]['quantity'], 2)
        # User A must NOT see RELIANCE
        self.assertNotIn('RELIANCE', [h['symbol'] for h in data_a['holdings']])

        # 2. Query User B portfolio summary
        summary_b_res = self.client.get('/api/portfolio/summary', headers=headers_b)
        self.assertEqual(summary_b_res.status_code, 200)
        data_b = json.loads(summary_b_res.data)['data']

        # User B checks
        self.assertEqual(data_b['holdings_count'], 1)
        self.assertEqual(data_b['holdings'][0]['symbol'], 'RELIANCE')
        self.assertEqual(data_b['holdings'][0]['quantity'], 1)
        # User B must NOT see TCS
        self.assertNotIn('TCS', [h['symbol'] for h in data_b['holdings']])

        # 3. Check individual balances are isolated
        tcs_cost = json.loads(res_buy_a.data)['data']['transaction']['total_amount']
        rel_cost = json.loads(res_buy_b.data)['data']['transaction']['total_amount']

        self.assertEqual(data_a['virtual_cash'], round(10000.0 - tcs_cost, 2))
        self.assertEqual(data_b['virtual_cash'], round(10000.0 - rel_cost, 2))

        # 4. Check Transaction Isolation
        tx_a = json.loads(self.client.get('/api/portfolio/transactions', headers=headers_a).data)['data']
        tx_b = json.loads(self.client.get('/api/portfolio/transactions', headers=headers_b).data)['data']

        self.assertEqual(len(tx_a), 1)
        self.assertEqual(tx_a[0]['symbol'], 'TCS')

        self.assertEqual(len(tx_b), 1)
        self.assertEqual(tx_b[0]['symbol'], 'RELIANCE')

    def test_unauthenticated_portfolio_page_redirects_to_login(self):
        """Verify accessing /portfolio without being logged in redirects to /login."""
        res = self.client.get('/portfolio')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers.get('Location', ''))

if __name__ == '__main__':
    unittest.main()
