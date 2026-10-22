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
from backend.app.services.wallet_service import WalletService

class VirtualMoneyWalletTestCase(unittest.TestCase):
    """
    Test suite verifying the virtual-money paper trading wallet system:
    1. New registration automatically initializes ₹10,000 virtual balance.
    2. Two distinct users (User A & User B) both start with ₹10,000.
    3. Changing User A's balance does NOT alter User B's balance.
    4. Admin can adjust user's balance via backend API.
    5. Normal users cannot access admin wallet adjustment endpoint (403 Forbidden).
    6. Negative balance prevention.
    7. Existing users without prior wallet safely get ₹10,000 upon access.
    """

    def setUp(self):
        """Set up in-memory testing application and client."""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Seed an admin user
        self.admin = User(
            username='system_admin',
            email='admin@stocksense.ai',
            full_name='System Admin',
            role='admin'
        )
        self.admin.set_password('AdminPassword123!')
        db.session.add(self.admin)
        db.session.commit()

        # Generate admin token
        admin_login = self.client.post('/api/auth/login', json={
            'identifier': 'system_admin',
            'password': 'AdminPassword123!',
            'role': 'admin'
        })
        self.admin_token = json.loads(admin_login.data)['data']['token']

    def tearDown(self):
        """Clean up in-memory database after tests."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_new_user_registration_receives_10000_virtual_cash(self):
        """Verify newly registered user automatically receives ₹10,000 virtual money in database."""
        res = self.client.post('/api/auth/register', json={
            'username': 'trader_charlie',
            'email': 'charlie@test.com',
            'password': 'password123',
            'full_name': 'Charlie Trader'
        })
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        token = data['data']['token']
        self.assertEqual(data['data']['user']['virtual_cash'], 10000.0)

        # Check database directly
        user = User.query.filter_by(username='trader_charlie').first()
        self.assertIsNotNone(user)
        self.assertIsNotNone(user.wallet)
        self.assertEqual(user.wallet.virtual_cash, 10000.0)

        # Check /api/user/wallet endpoint
        headers = {'Authorization': f'Bearer {token}'}
        wallet_res = self.client.get('/api/user/wallet', headers=headers)
        self.assertEqual(wallet_res.status_code, 200)
        wallet_data = json.loads(wallet_res.data)
        self.assertEqual(wallet_data['data']['virtual_cash'], 10000.0)
        self.assertEqual(wallet_data['data']['formatted_virtual_cash'], '₹10,000.00')

    def test_two_users_both_start_with_10000(self):
        """Verify User A and User B both independently receive ₹10,000 on registration."""
        # Register User A
        res_a = self.client.post('/api/auth/register', json={
            'username': 'user_a',
            'email': 'usera@test.com',
            'password': 'password123',
            'full_name': 'User Alpha'
        })
        self.assertEqual(res_a.status_code, 201)
        data_a = json.loads(res_a.data)['data']

        # Register User B
        res_b = self.client.post('/api/auth/register', json={
            'username': 'user_b',
            'email': 'userb@test.com',
            'password': 'password123',
            'full_name': 'User Beta'
        })
        self.assertEqual(res_b.status_code, 201)
        data_b = json.loads(res_b.data)['data']

        # Verify both start with 10,000
        self.assertEqual(data_a['user']['virtual_cash'], 10000.0)
        self.assertEqual(data_b['user']['virtual_cash'], 10000.0)

        user_a = User.query.filter_by(username='user_a').first()
        user_b = User.query.filter_by(username='user_b').first()

        self.assertEqual(user_a.wallet.virtual_cash, 10000.0)
        self.assertEqual(user_b.wallet.virtual_cash, 10000.0)
        self.assertNotEqual(user_a.wallet.id, user_b.wallet.id)

    def test_changing_user_a_does_not_affect_user_b(self):
        """
        CRITICAL TEST:
        Changing User A's virtual cash must NEVER alter User B's balance.
        """
        # 1. Register User A and User B
        self.client.post('/api/auth/register', json={
            'username': 'user_a',
            'email': 'usera@test.com',
            'password': 'password123',
            'full_name': 'User Alpha'
        })
        self.client.post('/api/auth/register', json={
            'username': 'user_b',
            'email': 'userb@test.com',
            'password': 'password123',
            'full_name': 'User Beta'
        })

        user_a = User.query.filter_by(username='user_a').first()
        user_b = User.query.filter_by(username='user_b').first()

        self.assertEqual(user_a.virtual_cash, 10000.0)
        self.assertEqual(user_b.virtual_cash, 10000.0)

        # 2. Modify User A's balance via WalletService (e.g. deduct ₹3,500)
        w_a, msg, code = WalletService.adjust_balance(user_a.id, -3500.0)
        self.assertEqual(code, 200)
        self.assertEqual(w_a['virtual_cash'], 6500.0)

        # 3. Reload both from database
        db.session.expire_all()
        refreshed_a = db.session.get(User, user_a.id)
        refreshed_b = db.session.get(User, user_b.id)

        # User A's balance changed to 6,500
        self.assertEqual(refreshed_a.virtual_cash, 6500.0)
        self.assertEqual(refreshed_a.wallet.virtual_cash, 6500.0)

        # User B's balance REMAINED strictly 10,000.0
        self.assertEqual(refreshed_b.virtual_cash, 10000.0)
        self.assertEqual(refreshed_b.wallet.virtual_cash, 10000.0)

        # 4. Modify User A again via admin adjustment (+ ₹15,000)
        headers = {'Authorization': f'Bearer {self.admin_token}'}
        admin_res = self.client.post(f'/api/admin/users/{user_a.id}/wallet', json={
            'amount': 15000.0,
            'reason': 'Bonus paper funds'
        }, headers=headers)
        self.assertEqual(admin_res.status_code, 200)

        db.session.expire_all()
        refreshed_a2 = db.session.get(User, user_a.id)
        refreshed_b2 = db.session.get(User, user_b.id)

        # User A is now 6,500 + 15,000 = 21,500
        self.assertEqual(refreshed_a2.virtual_cash, 21500.0)
        # User B STILL remains unchanged at 10,000
        self.assertEqual(refreshed_b2.virtual_cash, 10000.0)

    def test_admin_set_balance_api(self):
        """Test admin explicitly overwriting user's virtual balance."""
        res_user = self.client.post('/api/auth/register', json={
            'username': 'target_trader',
            'email': 'target@test.com',
            'password': 'password123',
            'full_name': 'Target Trader'
        })
        user_id = json.loads(res_user.data)['data']['user']['id']

        headers = {'Authorization': f'Bearer {self.admin_token}'}
        set_res = self.client.post(f'/api/admin/users/{user_id}/wallet', json={
            'set_balance': 50000.0,
            'reason': 'Contest winner prize'
        }, headers=headers)
        self.assertEqual(set_res.status_code, 200)
        data = json.loads(set_res.data)
        self.assertEqual(data['data']['wallet']['virtual_cash'], 50000.0)

        user = db.session.get(User, user_id)
        self.assertEqual(user.virtual_cash, 50000.0)

    def test_unauthorized_user_cannot_access_admin_wallet_api(self):
        """Test standard user attempting to access admin wallet adjustment endpoint is blocked (403)."""
        res_a = self.client.post('/api/auth/register', json={
            'username': 'normal_user',
            'email': 'normal@test.com',
            'password': 'password123',
            'full_name': 'Normal User'
        })
        user_token = json.loads(res_a.data)['data']['token']
        user_id = json.loads(res_a.data)['data']['user']['id']

        headers = {'Authorization': f'Bearer {user_token}'}
        tamper_res = self.client.post(f'/api/admin/users/{user_id}/wallet', json={
            'amount': 999999.0
        }, headers=headers)
        self.assertEqual(tamper_res.status_code, 403)

    def test_negative_balance_prevention(self):
        """Test that wallet balance cannot be set below zero."""
        user = User(username='poor_user', email='poor@test.com', password_hash='hash', role='user')
        db.session.add(user)
        db.session.commit()

        # Attempt to deduct 15,000 from 10,000
        res, msg, code = WalletService.adjust_balance(user.id, -15000.0)
        self.assertIsNone(res)
        self.assertEqual(code, 400)
        self.assertIn("Insufficient virtual funds", msg)

        # Attempt to set negative balance
        res2, msg2, code2 = WalletService.update_balance(user.id, -500.0)
        self.assertIsNone(res2)
        self.assertEqual(code2, 400)

    def test_existing_user_without_wallet_handled_safely(self):
        """Test that legacy user created before wallet existed gets safely initialized with ₹10,000."""
        # Create user directly without creating wallet
        legacy_user = User(
            username='legacy_user',
            email='legacy@test.com',
            password_hash='dummyhash',
            role='user'
        )
        db.session.add(legacy_user)
        db.session.commit()

        # Query user virtual_cash property
        self.assertEqual(legacy_user.virtual_cash, 10000.0)

        # Call WalletService
        w = WalletService.get_or_create_wallet(legacy_user.id)
        self.assertEqual(w.virtual_cash, 10000.0)
        self.assertIsNotNone(w.id)

if __name__ == '__main__':
    unittest.main()
