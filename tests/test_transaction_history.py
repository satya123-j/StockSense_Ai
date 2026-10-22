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

class TransactionHistoryTestCase(unittest.TestCase):
    """
    Test suite for Paper Trading Transaction History:
    1. Automatic recording of BUY orders in database.
    2. Automatic recording of SELL orders in database.
    3. Retrieval of transaction fields:
       - Date/Time (created_at)
       - Stock Symbol (symbol)
       - BUY / SELL (transaction_type)
       - Quantity (quantity)
       - Execution Price (price)
       - Total Amount (total_amount)
    4. Strict multi-user transaction isolation:
       - User A cannot see User B's transactions.
       - User B cannot see User A's transactions.
       - User C (new user) has an empty list of transactions.
    5. Persistence across database session reloads.
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
            'full_name': f'Trader {username}'
        })
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)['data']
        token = data['token']
        user_id = data['user']['id']
        headers = {'Authorization': f'Bearer {token}'}
        return user_id, token, headers

    def test_automatic_buy_and_sell_transaction_recording(self):
        """Verify BUY and SELL transactions are automatically created in the database."""
        user_id, token, headers = self._register('trader_history_1', 'th1@paper.test')

        # 1. Initially 0 transactions
        res0 = self.client.get('/api/portfolio/transactions', headers=headers)
        self.assertEqual(res0.status_code, 200)
        self.assertEqual(len(json.loads(res0.data)['data']), 0)

        # 2. Execute BUY: 2 shares of TCS
        buy_res = self.client.post('/api/portfolio/buy', json={
            'symbol': 'TCS',
            'quantity': 2
        }, headers=headers)
        self.assertEqual(buy_res.status_code, 200)

        # 3. Verify BUY transaction appears in history
        res1 = self.client.get('/api/portfolio/transactions', headers=headers)
        self.assertEqual(res1.status_code, 200)
        txs1 = json.loads(res1.data)['data']
        self.assertEqual(len(txs1), 1)

        buy_tx = txs1[0]
        self.assertEqual(buy_tx['symbol'], 'TCS')
        self.assertEqual(buy_tx['transaction_type'], 'BUY')
        self.assertEqual(buy_tx['quantity'], 2)
        self.assertGreater(buy_tx['price'], 0)
        self.assertEqual(buy_tx['total_amount'], round(buy_tx['price'] * 2, 2))
        self.assertIsNotNone(buy_tx['created_at'])

        # 4. Execute SELL: 1 share of TCS
        sell_res = self.client.post('/api/portfolio/sell', json={
            'symbol': 'TCS',
            'quantity': 1
        }, headers=headers)
        self.assertEqual(sell_res.status_code, 200)

        # 5. Verify SELL transaction appears in history (total 2 transactions)
        res2 = self.client.get('/api/portfolio/transactions', headers=headers)
        self.assertEqual(res2.status_code, 200)
        txs2 = json.loads(res2.data)['data']
        self.assertEqual(len(txs2), 2)

        # Newest transaction is SELL
        sell_tx = txs2[0]
        self.assertEqual(sell_tx['symbol'], 'TCS')
        self.assertEqual(sell_tx['transaction_type'], 'SELL')
        self.assertEqual(sell_tx['quantity'], 1)
        self.assertGreater(sell_tx['price'], 0)
        self.assertEqual(sell_tx['total_amount'], round(sell_tx['price'] * 1, 2))
        self.assertIsNotNone(sell_tx['created_at'])

        # Direct database query check
        db_txs = Transaction.query.filter_by(user_id=user_id).all()
        self.assertEqual(len(db_txs), 2)

    def test_multi_user_transaction_isolation(self):
        """
        Verify strict transaction isolation across multiple users:
        - User A executes 1 BUY (TCS) and 1 SELL (TCS).
        - User B executes 1 BUY (INFY).
        - User C (brand new user) has 0 transactions.
        - User A sees ONLY TCS transactions.
        - User B sees ONLY INFY transaction.
        - User C sees 0 transactions.
        """
        id_a, token_a, h_a = self._register('trader_a', 'a@tx.test')
        id_b, token_b, h_b = self._register('trader_b', 'b@tx.test')
        id_c, token_c, h_c = self._register('trader_c', 'c@tx.test')

        # User A trades TCS
        self.client.post('/api/portfolio/buy', json={'symbol': 'TCS', 'quantity': 2}, headers=h_a)
        self.client.post('/api/portfolio/sell', json={'symbol': 'TCS', 'quantity': 1}, headers=h_a)

        # User B trades INFY
        self.client.post('/api/portfolio/buy', json={'symbol': 'INFY', 'quantity': 1}, headers=h_b)

        # Query User A transactions
        tx_a = json.loads(self.client.get('/api/portfolio/transactions', headers=h_a).data)['data']
        self.assertEqual(len(tx_a), 2)
        for t in tx_a:
            self.assertEqual(t['symbol'], 'TCS')
            self.assertNotEqual(t['symbol'], 'INFY')
            self.assertEqual(t['user_id'], id_a)

        # Query User B transactions
        tx_b = json.loads(self.client.get('/api/portfolio/transactions', headers=h_b).data)['data']
        self.assertEqual(len(tx_b), 1)
        self.assertEqual(tx_b[0]['symbol'], 'INFY')
        self.assertEqual(tx_b[0]['user_id'], id_b)

        # Query User C transactions (must be completely empty)
        tx_c = json.loads(self.client.get('/api/portfolio/transactions', headers=h_c).data)['data']
        self.assertEqual(len(tx_c), 0)

    def test_transaction_persistence_across_session(self):
        """Verify transaction records persist across database session reloads."""
        id_a, token_a, h_a = self._register('persist_user', 'persist@tx.test')

        # Execute 1 buy of RELIANCE
        self.client.post('/api/portfolio/buy', json={'symbol': 'RELIANCE', 'quantity': 1}, headers=h_a)

        # Force database session reset
        db.session.expire_all()
        db.session.remove()

        # Re-query transactions
        txs = json.loads(self.client.get('/api/portfolio/transactions', headers=h_a).data)['data']
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0]['symbol'], 'RELIANCE')
        self.assertEqual(txs[0]['transaction_type'], 'BUY')

if __name__ == '__main__':
    unittest.main()
