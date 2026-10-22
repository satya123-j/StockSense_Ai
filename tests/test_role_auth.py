import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.app import create_app
from backend.app.extensions import db
from backend.app.models.user import User

class RoleBasedAuthTestCase(unittest.TestCase):
    """
    Test suite for Role-Based Authentication in StockSense AI.
    Tests:
    1. Database role persistence on User model
    2. User registration default role ('user')
    3. Normal user login via User Login (200 OK)
    4. Admin login via Admin Login (200 OK)
    5. Normal user attempting Admin Login tab -> 403 Forbidden
    6. Admin user attempting User Login tab -> 403 Forbidden
    7. Unauthenticated access to admin routes -> 401 / redirect
    8. Normal user attempting access to admin view route /admin -> 403 Forbidden
    9. Normal user attempting access to admin API route /api/admin/status -> 403 Forbidden
    10. Admin successfully accessing /admin (200 OK)
    11. Admin successfully accessing /api/admin/status (200 OK)
    12. Admin restricted from normal user portfolio features -> 403 Forbidden
    """

    def setUp(self):
        """Set up in-memory testing application and client."""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Seed 1 standard User and 1 Admin
        self.normal_user = User(
            username='trader_alice',
            email='alice@stocksense.ai',
            full_name='Alice Trader',
            role='user'
        )
        self.normal_user.set_password('Password123!')
        db.session.add(self.normal_user)

        self.admin_user = User(
            username='admin_bob',
            email='bob_admin@stocksense.ai',
            full_name='Bob Administrator',
            role='admin'
        )
        self.admin_user.set_password('AdminPassword123!')
        db.session.add(self.admin_user)
        db.session.commit()

    def tearDown(self):
        """Clean up in-memory database after tests."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_database_role_fields(self):
        """Verify role fields and helper methods on User model."""
        user = User.query.filter_by(username='trader_alice').first()
        admin = User.query.filter_by(username='admin_bob').first()

        self.assertEqual(user.role, 'user')
        self.assertTrue(user.is_user())
        self.assertFalse(user.is_admin())
        self.assertEqual(user.to_dict()['role'], 'user')

        self.assertEqual(admin.role, 'admin')
        self.assertTrue(admin.is_admin())
        self.assertFalse(admin.is_user())
        self.assertEqual(admin.to_dict()['role'], 'admin')

    def test_registration_always_assigns_user_role(self):
        """Verify that public registration always defaults to role='user'."""
        res = self.client.post('/api/auth/register', json={
            'username': 'new_investor',
            'email': 'new@investor.com',
            'password': 'password123',
            'full_name': 'New Investor',
            'role': 'admin' # Malicious attempt to elevate role during public registration
        })
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertEqual(data['data']['user']['role'], 'user')

        created_user = User.query.filter_by(username='new_investor').first()
        self.assertEqual(created_user.role, 'user')

    def test_normal_user_login_success(self):
        """Test normal user logging in via User Login role selection."""
        res = self.client.post('/api/auth/login', json={
            'identifier': 'trader_alice',
            'password': 'Password123!',
            'role': 'user'
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['data']['user']['role'], 'user')
        self.assertEqual(data['data']['redirect_url'], '/dashboard')
        self.assertIn('token', data['data'])

    def test_admin_login_success(self):
        """Test admin user logging in via Admin Login role selection."""
        res = self.client.post('/api/auth/login', json={
            'identifier': 'admin_bob',
            'password': 'AdminPassword123!',
            'role': 'admin'
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['data']['user']['role'], 'admin')
        self.assertEqual(data['data']['redirect_url'], '/admin')
        self.assertIn('token', data['data'])

    def test_normal_user_cannot_login_as_admin(self):
        """Test that a standard user selecting 'Admin Login' is rejected by the backend."""
        res = self.client.post('/api/auth/login', json={
            'identifier': 'trader_alice',
            'password': 'Password123!',
            'role': 'admin' # Normal user attempting to use Admin Login
        })
        self.assertEqual(res.status_code, 403)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn("Administrator privileges required", data['message'])

    def test_admin_cannot_login_as_normal_user(self):
        """Test that an admin account cannot log in via the normal User Login tab."""
        res = self.client.post('/api/auth/login', json={
            'identifier': 'admin_bob',
            'password': 'AdminPassword123!',
            'role': 'user' # Admin user attempting to use standard User Login
        })
        self.assertEqual(res.status_code, 403)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn("Admin accounts cannot log in as standard users", data['message'])

    def test_unauthenticated_access_to_admin_routes(self):
        """Test unauthenticated requests to admin routes are blocked."""
        # API route returns 401
        res_api = self.client.get('/api/admin/status')
        self.assertEqual(res_api.status_code, 401)

        # View route redirects to /login
        res_view = self.client.get('/admin')
        self.assertEqual(res_view.status_code, 302)
        self.assertIn('/login', res_view.headers['Location'])

    def test_unauthorized_user_attempting_to_access_admin_routes(self):
        """
        SECURITY TEST:
        Normal authenticated user attempting to access:
        1. Admin API route /api/admin/status -> Must return 403 Forbidden
        2. Admin HTML view route /admin -> Must return 403 Forbidden with 403.html
        """
        # 1. Login as standard user
        login_res = self.client.post('/api/auth/login', json={
            'identifier': 'trader_alice',
            'password': 'Password123!',
            'role': 'user'
        })
        user_token = json.loads(login_res.data)['data']['token']
        headers = {'Authorization': f'Bearer {user_token}'}

        # 2. Normal user calls Admin API endpoint
        res_api = self.client.get('/api/admin/status', headers=headers)
        self.assertEqual(res_api.status_code, 403)
        api_data = json.loads(res_api.data)
        self.assertEqual(api_data['status'], 'error')
        self.assertIn("Administrator privileges required", api_data['message'])

        # 3. Normal user manually navigates to /admin in browser
        # Set cookie or pass Authorization header
        self.client.set_cookie('jwt_token', user_token)
        res_view = self.client.get('/admin', headers=headers)
        self.assertEqual(res_view.status_code, 403)
        self.assertIn(b"ACCESS FORBIDDEN", res_view.data)
        self.assertIn(b"Administrator Access Required", res_view.data)

    def test_admin_access_to_admin_routes(self):
        """Test that authenticated Admin can access protected admin view and API endpoints."""
        # 1. Login as admin
        login_res = self.client.post('/api/auth/login', json={
            'identifier': 'admin_bob',
            'password': 'AdminPassword123!',
            'role': 'admin'
        })
        admin_token = json.loads(login_res.data)['data']['token']
        headers = {'Authorization': f'Bearer {admin_token}'}

        # 2. Access Admin API endpoint /api/admin/status
        res_api = self.client.get('/api/admin/status', headers=headers)
        self.assertEqual(res_api.status_code, 200)
        api_data = json.loads(res_api.data)
        self.assertEqual(api_data['status'], 'success')
        self.assertEqual(api_data['data']['role'], 'admin')
        self.assertEqual(api_data['data']['username'], 'admin_bob')

        # 3. Access Admin View /admin
        self.client.set_cookie('jwt_token', admin_token)
        res_view = self.client.get('/admin', headers=headers)
        self.assertEqual(res_view.status_code, 200)
        self.assertIn(b"Admin Portal", res_view.data)
        self.assertIn(b"Administrator Area Verified", res_view.data)

    def test_admin_restricted_from_user_portfolio_features(self):
        """
        Test that an Admin account cannot act as a normal user in user-only features (e.g. watchlist).
        Admin: 'Cannot be treated as a normal user'.
        """
        login_res = self.client.post('/api/auth/login', json={
            'identifier': 'admin_bob',
            'password': 'AdminPassword123!',
            'role': 'admin'
        })
        admin_token = json.loads(login_res.data)['data']['token']
        headers = {'Authorization': f'Bearer {admin_token}'}

        # Attempt to access user watchlist API
        res_wl = self.client.get('/api/watchlist', headers=headers)
        self.assertEqual(res_wl.status_code, 403)
        wl_data = json.loads(res_wl.data)
        self.assertIn("Standard user account required", wl_data['message'])

if __name__ == '__main__':
    unittest.main()
