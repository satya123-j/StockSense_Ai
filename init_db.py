import os
from backend.app import create_app
from backend.app.extensions import db
from backend.app.models.user import User
from backend.app.models.watchlist import Watchlist
from backend.app.models.stock import StockMetadata, RecentView
from backend.app.models.wallet import Wallet
from backend.app.models.portfolio import Holding, Transaction
from backend.app.models.audit import AdminAuditLog
from backend.app.services.instrument_mapping_service import NSE_INSTRUMENTS_MASTER

def init_database():
    """Initializes database tables and populates initial stock dictionary."""
    app = create_app('development')
    with app.app_context():
        print(f"Connecting to database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print("Creating tables if they do not exist...")
        db.create_all()

        # Ensure role column exists if users table was already created
        try:
            with db.engine.connect() as conn:
                res = conn.execute(db.text("PRAGMA table_info(users)"))
                cols = [r[1] for r in res.fetchall()]
                if 'role' not in cols:
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))
                    conn.commit()
                    print("Added missing 'role' column to users table.")

                # Ensure realized_pnl column exists in transactions table
                res_tx = conn.execute(db.text("PRAGMA table_info(transactions)"))
                cols_tx = [r[1] for r in res_tx.fetchall()]
                if cols_tx and 'realized_pnl' not in cols_tx:
                    conn.execute(db.text("ALTER TABLE transactions ADD COLUMN realized_pnl FLOAT DEFAULT 0.0"))
                    conn.commit()
                    print("Added missing 'realized_pnl' column to transactions table.")
        except Exception as e:
            print(f"Schema check notice: {e}")

        # Ensure all existing users safely have an initialized virtual wallet
        users = User.query.all()
        for u in users:
            if not u.wallet:
                w = Wallet(user_id=u.id, virtual_cash=10000.0)
                db.session.add(w)
        db.session.commit()

        print("Tables created successfully: users, watchlist, stocks_metadata, recent_views, wallets.")

        # Seed Indian Stocks Metadata
        print("Seeding Indian stocks metadata...")
        seeded_count = 0
        for item in NSE_INSTRUMENTS_MASTER:
            existing = StockMetadata.query.filter_by(symbol=item['symbol']).first()
            if not existing:
                stock_meta = StockMetadata(
                    symbol=item['symbol'],
                    company_name=item['name'],
                    exchange=item.get('exchange', 'NSE'),
                    sector=item.get('sector', 'N/A'),
                    industry=item.get('industry', 'N/A')
                )
                db.session.add(stock_meta)
                seeded_count += 1

        db.session.commit()
        print(f"Successfully seeded {seeded_count} new stocks into metadata cache.")

        # Check for demo user
        demo_user = User.query.filter_by(username='demo_user').first()
        if not demo_user:
            demo_user = User(
                username='demo_user',
                email='demo@stocksense.ai',
                full_name='Demo Investor'
            )
            demo_user.set_password('password123')
            db.session.add(demo_user)
            db.session.commit()

            # Add default initial watchlist for demo user
            default_stocks = [
                ('RELIANCE', 'Reliance Industries Ltd', 'NSE'),
                ('TCS', 'Tata Consultancy Services Ltd', 'NSE'),
                ('HDFCBANK', 'HDFC Bank Ltd', 'NSE'),
                ('INFY', 'Infosys Ltd', 'NSE'),
                ('TATAMOTORS', 'Tata Motors Ltd', 'NSE')
            ]
            for sym, name, ex in default_stocks:
                w = Watchlist(user_id=demo_user.id, symbol=sym, company_name=name, exchange=ex, notes='Top market holding')
                db.session.add(w)
            db.session.commit()
            print("Created default demo user: 'demo_user' (password: 'password123') with starter watchlist.")

        print("[SUCCESS] Database initialization complete!")

if __name__ == '__main__':
    init_database()
