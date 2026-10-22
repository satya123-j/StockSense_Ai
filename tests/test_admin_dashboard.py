import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.app import create_app
from backend.app.extensions import db
from backend.app.models.user import User
from backend.app.models.wallet import Wallet
from backend.app.models.portfolio import Holding, Transaction
from backend.app.models.audit import AdminAuditLog
from backend.app.services.wallet_service import WalletService
from backend.app.services.paper_trading_service import PaperTradingService


class AdminDashboardTestCase(unittest.TestCase):
    """
    Comprehensive test suite for the StockSense AI Admin Dashboard:
    1. Admin Login & Role Verification
    2. Access Control & Authorization (401 for unauthenticated, 403 for normal users)
    3. User Management listing (ID, Name, Email, Reg Date, Role, Cash, Portfolio Value, P/L, NO passwords)
    4. User Details & Portfolio inspection (Holdings, Transactions, Audits, Valuation)
    5. Platform Paper Trading Activity Stream (BUY/SELL surveillance)
    6. Add Virtual Money Calculation (Current + Added = New Balance calculated on backend)
    7. Audit Trail verification (AdminAuditLog record creation and retrieval)
    8. Input validation and security restrictions
    """

    def setUp(self):
        """Set up isolated test application and database context."""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # 1. Create standard trader user
        self.normal_user = User(
            username='trader_alice',
            email='alice@example.com',
            full_name='Alice Trader',
            role='user'
        )
        self.normal_user.set_password('AlicePass123!')
        db.session.add(self.normal_user)
        db.session.commit()

        # Initialize Alice's wallet with ₹4,000 for realistic simulation
        self.alice_wallet = Wallet(user_id=self.normal_user.id, virtual_cash=4000.0)
        db.session.add(self.alice_wallet)

        # 2. Create second trader user
        self.second_user = User(
            username='trader_charlie',
            email='charlie@example.com',
            full_name='Charlie Trader',
            role='user'
        )
        self.second_user.set_password('CharliePass123!')
        db.session.add(self.second_user)
        db.session.commit()

        self.charlie_wallet = Wallet(user_id=self.second_user.id, virtual_cash=10000.0)
        db.session.add(self.charlie_wallet)

        # 3. Create Admin user
        self.admin_user = User(
            username='admin_boss',
            email='admin@stocksense.ai',
            full_name='Chief Administrator',
            role='admin'
        )
        self.admin_user.set_password('AdminMasterSecret999!')
        db.session.add(self.admin_user)
        db.session.commit()

        # Authenticate and obtain JWT tokens using AuthService to avoid session pollution in self.client
        from backend.app.services.auth_service import AuthService
        self.normal_token = AuthService.generate_token(self.normal_user)
        self.admin_token = AuthService.generate_token(self.admin_user)

    def tearDown(self):
        """Clean up database after each test."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # =========================================================================
    # 1. Admin Login & Authorization Tests
    # =========================================================================

    def test_admin_login_success(self):
        """Verify admin can log in and receives admin role."""
        res = self.client.post('/api/auth/login', json={
            'identifier': 'admin_boss',
            'password': 'AdminMasterSecret999!',
            'role': 'admin'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['data']['user']['role'], 'admin')
        self.assertTrue('token' in data['data'])

    def test_admin_status_endpoint(self):
        """Verify admin can access /api/admin/status."""
        res = self.client.get('/api/admin/status', headers={
            'Authorization': f'Bearer {self.admin_token}'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['data']['role'], 'admin')
        self.assertTrue(data['data']['authorized'])

    # =========================================================================
    # 2. Access Control Security Tests (Normal user blocked from Admin)
    # =========================================================================

    def test_unauthenticated_access_blocked(self):
        """Verify unauthenticated requests to admin endpoints return 401 or redirect."""
        # API request -> 401
        res = self.client.get('/api/admin/users')
        self.assertEqual(res.status_code, 401)

        # HTML page request -> 302 redirect to /login
        res_view = self.client.get('/admin')
        self.assertEqual(res_view.status_code, 302)

    def test_normal_user_blocked_from_admin_dashboard_view(self):
        """Verify normal user attempting to access /admin gets 403 Forbidden."""
        res = self.client.get('/admin', headers={
            'Authorization': f'Bearer {self.normal_token}'
        })
        self.assertEqual(res.status_code, 403)

    def test_normal_user_blocked_from_admin_apis(self):
        """Verify normal user is rejected with 403 on all admin APIs."""
        endpoints = [
            ('/api/admin/status', 'GET', None),
            ('/api/admin/users', 'GET', None),
            (f'/api/admin/users/{self.normal_user.id}', 'GET', None),
            ('/api/admin/activity', 'GET', None),
            (f'/api/admin/users/{self.normal_user.id}/add-money', 'POST', {'amount': 1000}),
            ('/api/admin/audit-logs', 'GET', None)
        ]

        for ep, method, payload in endpoints:
            if method == 'GET':
                res = self.client.get(ep, headers={'Authorization': f'Bearer {self.normal_token}'})
            else:
                res = self.client.post(ep, json=payload, headers={'Authorization': f'Bearer {self.normal_token}'})

            self.assertEqual(
                res.status_code, 403,
                f"Endpoint {ep} should have returned 403 Forbidden for normal user, got {res.status_code}"
            )
            data = res.get_json()
            self.assertIn("Administrator privileges required", data['message'])

    # =========================================================================
    # 3. User Management Listing (Passwords strictly protected)
    # =========================================================================

    def test_admin_get_all_users_structure_and_no_passwords(self):
        """
        Verify admin can retrieve all users with:
        User ID, Name, Email, Reg Date, Role, Virtual Cash, Portfolio Value, Total P/L.
        Passwords must NOT be exposed.
        """
        res = self.client.get('/api/admin/users', headers={
            'Authorization': f'Bearer {self.admin_token}'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        users = data['data']

        self.assertGreaterEqual(len(users), 3)  # alice, charlie, admin

        alice_entry = next((u for u in users if u['username'] == 'trader_alice'), None)
        self.assertIsNotNone(alice_entry)
        self.assertEqual(alice_entry['id'], self.normal_user.id)
        self.assertEqual(alice_entry['name'], 'Alice Trader')
        self.assertEqual(alice_entry['email'], 'alice@example.com')
        self.assertEqual(alice_entry['role'], 'user')
        self.assertEqual(alice_entry['virtual_cash'], 4000.0)
        self.assertIn('portfolio_value', alice_entry)
        self.assertIn('total_pnl', alice_entry)
        self.assertIn('registration_date', alice_entry)

        # STRICT SECURITY CHECK: Ensure password and password_hash are NEVER present
        for u in users:
            self.assertNotIn('password', u, "User password must not be exposed")
            self.assertNotIn('password_hash', u, "User password_hash must not be exposed")

    # =========================================================================
    # 4. User Details & Portfolio Inspection
    # =========================================================================

    def test_admin_view_user_details_and_portfolio(self):
        """
        Verify admin can inspect a specific user's complete profile,
        virtual cash, portfolio holdings, portfolio value, total P/L, and transactions.
        """
        # Seed a holding and transaction for Alice
        holding = Holding(
            user_id=self.normal_user.id,
            symbol='TCS',
            company_name='Tata Consultancy Services Ltd',
            exchange='NSE',
            quantity=5,
            average_buy_price=3500.0,
            total_invested=17500.0
        )
        db.session.add(holding)

        tx = Transaction(
            user_id=self.normal_user.id,
            symbol='TCS',
            company_name='Tata Consultancy Services Ltd',
            transaction_type='BUY',
            quantity=5,
            price=3500.0,
            total_amount=17500.0,
            status='COMPLETED'
        )
        db.session.add(tx)
        db.session.commit()

        res = self.client.get(f'/api/admin/users/{self.normal_user.id}', headers={
            'Authorization': f'Bearer {self.admin_token}'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()['data']

        # Verify user info
        self.assertEqual(data['user']['id'], self.normal_user.id)
        self.assertEqual(data['user']['username'], 'trader_alice')
        self.assertEqual(data['virtual_cash'], 4000.0)

        # Verify password is not in user dict
        self.assertNotIn('password', data['user'])
        self.assertNotIn('password_hash', data['user'])

        # Verify holdings
        self.assertGreaterEqual(len(data['holdings']), 1)
        h = data['holdings'][0]
        self.assertEqual(h['symbol'], 'TCS')
        self.assertEqual(h['quantity'], 5)

        # Verify transactions
        self.assertGreaterEqual(len(data['transactions']), 1)
        t = data['transactions'][0]
        self.assertEqual(t['symbol'], 'TCS')
        self.assertEqual(t['transaction_type'], 'BUY')

    def test_admin_view_nonexistent_user(self):
        """Verify 404 is returned when querying non-existent user ID."""
        res = self.client.get('/api/admin/users/99999', headers={
            'Authorization': f'Bearer {self.admin_token}'
        })
        self.assertEqual(res.status_code, 404)

    # =========================================================================
    # 5. User Activity Stream (Paper-trading surveillance)
    # =========================================================================

    def test_admin_view_trading_activity_stream(self):
        """
        Verify admin can monitor all user paper-trading BUY and SELL executions.
        """
        # Create BUY and SELL transactions
        tx_buy = Transaction(
            user_id=self.normal_user.id,
            symbol='INFY',
            company_name='Infosys Limited',
            transaction_type='BUY',
            quantity=10,
            price=1500.0,
            total_amount=15000.0,
            status='COMPLETED'
        )
        tx_sell = Transaction(
            user_id=self.second_user.id,
            symbol='RELIANCE',
            company_name='Reliance Industries Ltd',
            transaction_type='SELL',
            quantity=2,
            price=2900.0,
            total_amount=5800.0,
            realized_pnl=400.0,
            status='COMPLETED'
        )
        db.session.add(tx_buy)
        db.session.add(tx_sell)
        db.session.commit()

        res = self.client.get('/api/admin/activity', headers={
            'Authorization': f'Bearer {self.admin_token}'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()['data']

        self.assertGreaterEqual(len(data), 2)
        symbols = [item['symbol'] for item in data]
        self.assertIn('INFY', symbols)
        self.assertIn('RELIANCE', symbols)

        # Verify required activity fields
        item = next(i for i in data if i['symbol'] == 'INFY')
        self.assertEqual(item['user_id'], self.normal_user.id)
        self.assertEqual(item['username'], 'trader_alice')
        self.assertEqual(item['action'], 'BUY')
        self.assertEqual(item['quantity'], 10)
        self.assertEqual(item['price'], 1500.0)
        self.assertEqual(item['total_amount'], 15000.0)
        self.assertIn('formatted_date', item)

    # =========================================================================
    # 6. Add Virtual Money & Backend Calculation
    # =========================================================================

    def test_admin_add_virtual_money_calculation_and_balance_update(self):
        """
        Verify:
        Current balance: ₹4,000
        Admin adds: ₹5,000
        New balance: ₹9,000
        Backend performs the calculation and persists the update.
        """
        # Confirm initial balance
        wallet_before = Wallet.query.filter_by(user_id=self.normal_user.id).first()
        self.assertEqual(wallet_before.virtual_cash, 4000.0)

        # Admin adds ₹5,000
        res = self.client.post(f'/api/admin/users/{self.normal_user.id}/add-money', json={
            'amount': 5000.0,
            'reason': 'Paper trading competition allowance'
        }, headers={'Authorization': f'Bearer {self.admin_token}'})

        self.assertEqual(res.status_code, 200)
        data = res.get_json()['data']

        # Verify backend response calculation
        self.assertEqual(data['old_balance'], 4000.0)
        self.assertEqual(data['added_amount'], 5000.0)
        self.assertEqual(data['new_balance'], 9000.0)

        # Verify directly in database
        wallet_after = Wallet.query.filter_by(user_id=self.normal_user.id).first()
        self.assertEqual(wallet_after.virtual_cash, 9000.0)

        # Verify Charlie's balance remained completely isolated (unchanged at ₹10,000)
        charlie_wallet = Wallet.query.filter_by(user_id=self.second_user.id).first()
        self.assertEqual(charlie_wallet.virtual_cash, 10000.0)

    # =========================================================================
    # 7. Audit Trail Verification
    # =========================================================================

    def test_admin_money_addition_recorded_in_audit_log(self):
        """
        Verify that adding virtual money creates an AdminAuditLog record
        with admin_id, user_id, action_type, amount, and description.
        """
        res = self.client.post(f'/api/admin/users/{self.normal_user.id}/add-money', json={
            'amount': 2500.0,
            'reason': 'Bonus credit for simulation'
        }, headers={'Authorization': f'Bearer {self.admin_token}'})
        self.assertEqual(res.status_code, 200)

        # Check AdminAuditLog in database
        audit_record = AdminAuditLog.query.filter_by(
            admin_id=self.admin_user.id,
            user_id=self.normal_user.id
        ).order_by(AdminAuditLog.created_at.desc()).first()

        self.assertIsNotNone(audit_record)
        self.assertEqual(audit_record.action_type, 'ADD_VIRTUAL_CASH')
        self.assertEqual(audit_record.amount, 2500.0)
        self.assertIn("Bonus credit for simulation", audit_record.description)
        self.assertIn("trader_alice", audit_record.description)

        # Verify /api/admin/audit-logs endpoint returns this record
        log_res = self.client.get('/api/admin/audit-logs', headers={
            'Authorization': f'Bearer {self.admin_token}'
        })
        self.assertEqual(log_res.status_code, 200)
        log_data = log_res.get_json()['data']
        self.assertGreaterEqual(len(log_data), 1)

        first_log = log_data[0]
        self.assertEqual(first_log['admin_id'], self.admin_user.id)
        self.assertEqual(first_log['user_id'], self.normal_user.id)
        self.assertEqual(first_log['amount'], 2500.0)

    # =========================================================================
    # 8. Validation and Edge Cases
    # =========================================================================

    def test_add_money_validation_negative_or_zero(self):
        """Verify invalid or non-positive amounts are rejected with 400 Bad Request."""
        # Zero amount
        res1 = self.client.post(f'/api/admin/users/{self.normal_user.id}/add-money', json={
            'amount': 0
        }, headers={'Authorization': f'Bearer {self.admin_token}'})
        self.assertEqual(res1.status_code, 400)
        self.assertIn("positive", res1.get_json()['message'])

        # Negative amount
        res2 = self.client.post(f'/api/admin/users/{self.normal_user.id}/add-money', json={
            'amount': -100
        }, headers={'Authorization': f'Bearer {self.admin_token}'})
        self.assertEqual(res2.status_code, 400)

        # Invalid string
        res3 = self.client.post(f'/api/admin/users/{self.normal_user.id}/add-money', json={
            'amount': 'one thousand'
        }, headers={'Authorization': f'Bearer {self.admin_token}'})
        self.assertEqual(res3.status_code, 400)

        # Non-existent user
        res4 = self.client.post('/api/admin/users/88888/add-money', json={
            'amount': 500
        }, headers={'Authorization': f'Bearer {self.admin_token}'})
        self.assertEqual(res4.status_code, 404)


if __name__ == '__main__':
    unittest.main()
