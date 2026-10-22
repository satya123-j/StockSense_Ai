import unittest
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from backend.app import create_app
from backend.app.extensions import db
from backend.app.models.user import User
from backend.app.models.watchlist import Watchlist
from backend.app.services.stock_service import StockService
from backend.app.services.technical_analysis_service import TechnicalAnalysisService

class CompleteFlowAuditTestCase(unittest.TestCase):
    """
    Complete audit test executing the entire 50% milestone workflow:
    Register -> Login -> Dashboard/Indices -> Search TCS -> Quote ->
    Historical Candles -> Technical Analysis (RSI, MACD, MA) ->
    Add Watchlist -> View Watchlist -> Duplicate Check -> Remove -> Logout.
    """

    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_complete_student_project_milestone_flow(self):
        # 1. Register
        reg_payload = {
            'username': 'rahul_sharma',
            'email': 'rahul@example.com',
            'password': 'StrongPassword@2026',
            'full_name': 'Rahul Sharma'
        }
        res_reg = self.client.post('/api/auth/register', json=reg_payload)
        self.assertEqual(res_reg.status_code, 201)
        reg_data = json.loads(res_reg.data)
        self.assertEqual(reg_data['status'], 'success')
        self.assertIn('token', reg_data['data'])

        # Verify password is NOT stored as plain text
        user_in_db = User.query.filter_by(username='rahul_sharma').first()
        self.assertIsNotNone(user_in_db)
        self.assertNotEqual(user_in_db.password_hash, 'StrongPassword@2026')
        self.assertTrue(user_in_db.check_password('StrongPassword@2026'))

        # 2. Login
        login_payload = {
            'identifier': 'rahul_sharma',
            'password': 'StrongPassword@2026'
        }
        res_login = self.client.post('/api/auth/login', json=login_payload)
        self.assertEqual(res_login.status_code, 200)
        login_data = json.loads(res_login.data)
        token = login_data['data']['token']
        auth_headers = {'Authorization': f'Bearer {token}'}

        # 3. Protected Route /api/auth/me
        res_me = self.client.get('/api/auth/me', headers=auth_headers)
        self.assertEqual(res_me.status_code, 200)
        me_data = json.loads(res_me.data)['data']
        self.assertEqual(me_data['username'], 'rahul_sharma')
        self.assertEqual(me_data['email'], 'rahul@example.com')

        # 4. Market Overview (Indices on Dashboard)
        res_indices = self.client.get('/api/market/indices')
        self.assertEqual(res_indices.status_code, 200)
        indices_data = json.loads(res_indices.data)['data']
        self.assertGreaterEqual(len(indices_data), 2)

        # 5. Market Trading Session Status
        res_market_status = self.client.get('/api/market/status')
        self.assertEqual(res_market_status.status_code, 200)
        status_data = json.loads(res_market_status.data)['data']
        self.assertIn('is_market_open', status_data)
        self.assertIn('trading_hours', status_data)

        # 6. Stock Search for TCS
        res_search = self.client.get('/api/stocks/search?q=TCS')
        self.assertEqual(res_search.status_code, 200)
        search_results = json.loads(res_search.data)['data']
        self.assertGreater(len(search_results), 0)
        tcs_item = next((item for item in search_results if item['symbol'] == 'TCS'), None)
        self.assertIsNotNone(tcs_item)
        self.assertEqual(tcs_item['exchange'], 'NSE')

        # 7. Real Market Quote Retrieval for TCS
        res_quote = self.client.get('/api/stocks/TCS/quote')
        self.assertEqual(res_quote.status_code, 200)
        quote_data = json.loads(res_quote.data)['data']
        self.assertEqual(quote_data['symbol'], 'TCS')
        self.assertIn('current_price', quote_data)
        self.assertIn('open', quote_data)
        self.assertIn('previous_close', quote_data)
        self.assertIn('day_high', quote_data)
        self.assertIn('day_low', quote_data)
        self.assertIn('volume', quote_data)
        self.assertIn('fifty_two_week_high', quote_data)
        self.assertIn('fifty_two_week_low', quote_data)
        self.assertIn('timestamp', quote_data)
        self.assertIn('data_source', quote_data)
        self.assertFalse(quote_data.get('is_demo', False))

        # 8. Historical Candle Data for Charting (1mo, 1d)
        res_history = self.client.get('/api/stocks/TCS/history?range=1mo&interval=1d')
        self.assertEqual(res_history.status_code, 200)
        hist_data = json.loads(res_history.data)['data']
        self.assertEqual(hist_data['symbol'], 'TCS')
        self.assertIn('points', hist_data)
        self.assertGreater(len(hist_data['points']), 0)
        first_point = hist_data['points'][0]
        self.assertIn('date', first_point)
        self.assertIn('close', first_point)
        self.assertIn('open', first_point)
        self.assertIn('high', first_point)
        self.assertIn('low', first_point)

        # 9. Technical Analysis Indicators (RSI, MACD, MA20, MA50)
        res_tech = self.client.get('/api/stocks/TCS/technical-analysis')
        self.assertEqual(res_tech.status_code, 200)
        tech_data = json.loads(res_tech.data)['data']
        self.assertEqual(tech_data['symbol'], 'TCS')
        self.assertIn('latest', tech_data)
        self.assertIn('rsi', tech_data['latest'])
        self.assertIn('macd', tech_data['latest'])
        self.assertIn('macd_signal', tech_data['latest'])
        self.assertIn('macd_histogram', tech_data['latest'])
        self.assertIn('ma_20', tech_data['latest'])
        self.assertIn('ma_50', tech_data['latest'])
        self.assertIn('chart_series', tech_data)
        self.assertFalse(tech_data.get('is_demo', False))

        # 10. Add TCS to Watchlist
        res_add_wl = self.client.post('/api/watchlist', headers=auth_headers, json={
            'symbol': 'TCS',
            'company_name': 'Tata Consultancy Services Ltd'
        })
        self.assertEqual(res_add_wl.status_code, 201)

        # 11. Duplicate Watchlist Entry Prevention (409)
        res_dup_wl = self.client.post('/api/watchlist', headers=auth_headers, json={'symbol': 'TCS'})
        self.assertEqual(res_dup_wl.status_code, 409)

        # 12. Check in Watchlist Endpoint
        res_check = self.client.get('/api/watchlist/check/TCS', headers=auth_headers)
        self.assertEqual(res_check.status_code, 200)
        self.assertTrue(json.loads(res_check.data)['data']['is_saved'])

        # 13. View Watchlist with Live Enriched Market Quotes
        res_wl = self.client.get('/api/watchlist', headers=auth_headers)
        self.assertEqual(res_wl.status_code, 200)
        wl_items = json.loads(res_wl.data)['data']
        self.assertEqual(len(wl_items), 1)
        self.assertEqual(wl_items[0]['symbol'], 'TCS')
        self.assertIn('current_price', wl_items[0])
        self.assertIn('change', wl_items[0])
        self.assertIn('change_percent', wl_items[0])

        # 14. Remove TCS from Watchlist via DELETE /api/watchlist/<symbol>
        res_del_wl = self.client.delete('/api/watchlist/TCS', headers=auth_headers)
        self.assertEqual(res_del_wl.status_code, 200)

        # Verify Watchlist is now empty
        res_wl_empty = self.client.get('/api/watchlist', headers=auth_headers)
        self.assertEqual(len(json.loads(res_wl_empty.data)['data']), 0)

        # 15. Logout
        res_logout = self.client.post('/api/auth/logout', headers=auth_headers)
        self.assertEqual(res_logout.status_code, 200)

if __name__ == '__main__':
    unittest.main()
