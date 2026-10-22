import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.app import create_app
from backend.app.extensions import db
from backend.app.models.user import User
from backend.app.models.watchlist import Watchlist
from backend.app.services.stock_service import StockService
from backend.app.services.technical_analysis_service import TechnicalAnalysisService
from backend.app.services.instrument_mapping_service import InstrumentMappingService
from backend.app.services.upstox_service import UpstoxService

class StockSenseAPITestCase(unittest.TestCase):
    """Test suite for StockSense AI REST API endpoints and Upstox market data integration."""

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

    def test_user_registration_and_login(self):
        """Test complete registration and authentication flow."""
        # 1. Register
        reg_payload = {
            'username': 'testinvestor',
            'email': 'test@stocksense.ai',
            'password': 'password123',
            'full_name': 'Test Investor'
        }
        res = self.client.post('/api/auth/register', json=reg_payload)
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('token', data['data'])
        token = data['data']['token']

        # 2. Duplicate Username Check
        res_dup = self.client.post('/api/auth/register', json=reg_payload)
        self.assertEqual(res_dup.status_code, 409)

        # 3. Login
        login_payload = {
            'identifier': 'testinvestor',
            'password': 'password123'
        }
        res_login = self.client.post('/api/auth/login', json=login_payload)
        self.assertEqual(res_login.status_code, 200)
        login_data = json.loads(res_login.data)
        self.assertEqual(login_data['data']['user']['username'], 'testinvestor')

        # 4. Access Protected Route /api/auth/me
        headers = {'Authorization': f'Bearer {token}'}
        res_me = self.client.get('/api/auth/me', headers=headers)
        self.assertEqual(res_me.status_code, 200)
        me_data = json.loads(res_me.data)
        self.assertEqual(me_data['data']['email'], 'test@stocksense.ai')

        # 5. Access Protected Route without token -> 401
        fresh_client = self.app.test_client()
        res_unauth = fresh_client.get('/api/auth/me')
        self.assertEqual(res_unauth.status_code, 401)

    def test_instrument_mapping_service(self):
        """Test instrument mapping for major Indian stocks: TCS, INFY, RELIANCE, HDFCBANK, ICICIBANK, ITC."""
        test_symbols = ['TCS', 'INFY', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'ITC']
        for sym in test_symbols:
            inst = InstrumentMappingService.get_instrument(sym)
            self.assertIsNotNone(inst)
            self.assertEqual(inst['trading_symbol'], sym)
            self.assertTrue(inst['instrument_key'].startswith('NSE_EQ|'))
            self.assertEqual(inst['exchange'], 'NSE')

    def test_stock_search_and_overview(self):
        """Test Indian stock search for TCS, INFY, RELIANCE, HDFCBANK, ICICIBANK, ITC."""
        symbols_to_test = ['TCS', 'INFY', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'ITC']
        for sym in symbols_to_test:
            res_search = self.client.get(f'/api/stocks/search?q={sym}')
            self.assertEqual(res_search.status_code, 200)
            data = json.loads(res_search.data)
            self.assertGreater(len(data['data']), 0)
            found_symbols = [s['symbol'] for s in data['data']]
            self.assertIn(sym, found_symbols)

        # Quote Overview via /api/stocks/TCS/quote
        res_quote = self.client.get('/api/stocks/TCS/quote')
        self.assertEqual(res_quote.status_code, 200)
        q_data = json.loads(res_quote.data)['data']
        self.assertEqual(q_data['symbol'], 'TCS')
        self.assertIn('exchange', q_data)
        self.assertIn('data_source', q_data)
        self.assertIn('timestamp', q_data)
        self.assertIn('open', q_data)
        self.assertIn('previous_close', q_data)
        self.assertIn('day_high', q_data)
        self.assertIn('day_low', q_data)
        self.assertIn('volume', q_data)
        self.assertIn('fifty_two_week_high', q_data)
        self.assertIn('fifty_two_week_low', q_data)

    def test_invalid_stock_symbol_returns_404(self):
        """Test that searching an invalid non-existent symbol returns 404 without mock values."""
        res = self.client.get('/api/stocks/INVALID_NONEXISTENT_XYZ_999/quote')
        self.assertEqual(res.status_code, 404)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'error')

    def test_stock_history_endpoint(self):
        """Test historical price candle endpoint for multiple supported timeframes."""
        timeframes = ['1d', '1w', '1mo', '6mo', '1y']
        for tf in timeframes:
            res = self.client.get(f'/api/stocks/TCS/history?range={tf}')
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data)['data']
            self.assertIn('symbol', data)
            self.assertIn('points', data)
            self.assertIn('data_source', data)

    def test_market_status_endpoint(self):
        """Test Indian market session status endpoint."""
        res = self.client.get('/api/market/status')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)['data']
        self.assertIn('is_market_open', data)
        self.assertIn('current_time_ist', data)
        self.assertIn('trading_hours', data)
        self.assertIn('session_name', data)

    def test_market_indices(self):
        """Test Indian Market Indices endpoint."""
        res = self.client.get('/api/market/indices')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)['data']
        self.assertGreaterEqual(len(data), 2)
        symbols = [idx['symbol'] for idx in data]
        self.assertIn('^NSEI', symbols)
        self.assertIn('^BSESN', symbols)

    def test_technical_indicators_calculation(self):
        """Test Technical Analysis Service & endpoint for TCS, INFY, and RELIANCE."""
        test_stocks = ['TCS', 'INFY', 'RELIANCE']
        for sym in test_stocks:
            res = self.client.get(f'/api/stocks/{sym}/technical-analysis')
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data)['data']
            self.assertEqual(data['symbol'], sym)
            self.assertIn('timestamp', data)
            self.assertIn('latest', data)
            self.assertIn('rsi', data['latest'])
            self.assertIn('macd', data['latest'])
            self.assertIn('macd_signal', data['latest'])
            self.assertIn('macd_histogram', data['latest'])
            self.assertIn('ma_20', data['latest'])
            self.assertIn('ma_50', data['latest'])
            self.assertIn('chart_series', data)
            self.assertFalse(data.get('is_demo', False))

    def test_watchlist_operations(self):
        """Test Watchlist Add, Enriched Fetch, Duplicate Prevention, and Delete operations."""
        # 1. Test unauthenticated access returns 401
        res_unauth = self.client.get('/api/watchlist')
        self.assertEqual(res_unauth.status_code, 401)

        # 2. Create User 1 & Token
        user1 = User(username='watchlistuser1', email='wl1@stocksense.ai', full_name='WL User One')
        user1.set_password('password123')
        db.session.add(user1)
        db.session.commit()

        from backend.app.services.auth_service import AuthService
        token1 = AuthService.generate_token(user1.id)
        headers1 = {'Authorization': f'Bearer {token1}'}

        # 3. Add Stock INFY
        add_res = self.client.post('/api/watchlist', headers=headers1, json={
            'symbol': 'INFY',
            'company_name': 'Infosys Ltd'
        })
        self.assertEqual(add_res.status_code, 201)

        # 4. Check duplicate prevention (409)
        dup_res = self.client.post('/api/watchlist', headers=headers1, json={'symbol': 'INFY'})
        self.assertEqual(dup_res.status_code, 409)

        # 5. Add second stock TCS
        add_tcs = self.client.post('/api/watchlist', headers=headers1, json={
            'symbol': 'TCS',
            'company_name': 'Tata Consultancy Services Ltd'
        })
        self.assertEqual(add_tcs.status_code, 201)

        # 6. Check is_in_watchlist endpoint
        check_res = self.client.get('/api/watchlist/check/INFY', headers=headers1)
        self.assertEqual(check_res.status_code, 200)
        self.assertTrue(json.loads(check_res.data)['data']['is_saved'])

        # 7. Get Watchlist with enriched live market quotes
        get_res = self.client.get('/api/watchlist', headers=headers1)
        self.assertEqual(get_res.status_code, 200)
        items = json.loads(get_res.data)['data']
        self.assertEqual(len(items), 2)
        symbols = [item['symbol'] for item in items]
        self.assertIn('INFY', symbols)
        self.assertIn('TCS', symbols)
        self.assertIn('current_price', items[0])
        self.assertIn('change', items[0])
        self.assertIn('change_percent', items[0])

        # 8. User 2 Isolation: User 2 has empty watchlist
        user2 = User(username='watchlistuser2', email='wl2@stocksense.ai', full_name='WL User Two')
        user2.set_password('password123')
        db.session.add(user2)
        db.session.commit()
        token2 = AuthService.generate_token(user2.id)
        headers2 = {'Authorization': f'Bearer {token2}'}
        get_res2 = self.client.get('/api/watchlist', headers=headers2)
        self.assertEqual(len(json.loads(get_res2.data)['data']), 0)

        # 9. Delete Stock by Symbol using DELETE /api/watchlist/<symbol>
        del_sym_res = self.client.delete('/api/watchlist/TCS', headers=headers1)
        self.assertEqual(del_sym_res.status_code, 200)

        # 10. Delete Stock by Symbol using DELETE /api/watchlist/INFY
        del_infy_res = self.client.delete('/api/watchlist/INFY', headers=headers1)
        self.assertEqual(del_infy_res.status_code, 200)

        # 11. Verify Watchlist is now empty
        get_empty = self.client.get('/api/watchlist', headers=headers1)
        self.assertEqual(len(json.loads(get_empty.data)['data']), 0)

if __name__ == '__main__':
    unittest.main()
