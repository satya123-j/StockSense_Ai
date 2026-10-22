from datetime import datetime
from backend.app.extensions import db

class Holding(db.Model):
    """
    Portfolio holding model for user paper trading.
    Tracks total shares held, weighted average buy price, and total capital invested.
    """
    __tablename__ = 'holdings'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    symbol = db.Column(db.String(20), nullable=False, index=True)
    company_name = db.Column(db.String(150), nullable=True)
    exchange = db.Column(db.String(20), default='NSE', nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    average_buy_price = db.Column(db.Float, nullable=False, default=0.0)
    total_invested = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'symbol', name='uq_user_symbol_holding'),
    )

    def to_dict(self):
        """Converts holding to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'symbol': self.symbol,
            'company_name': self.company_name or self.symbol,
            'exchange': self.exchange,
            'quantity': self.quantity,
            'average_buy_price': round(self.average_buy_price, 2),
            'formatted_average_price': f"₹{self.average_buy_price:,.2f}",
            'total_invested': round(self.total_invested, 2),
            'formatted_total_invested': f"₹{self.total_invested:,.2f}",
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<Holding user_id={self.user_id} symbol={self.symbol} qty={self.quantity} avg_price={self.average_buy_price}>'


class Transaction(db.Model):
    """
    Transaction log record for simulated paper-trading orders.
    Records every executed BUY (and future SELL) order.
    """
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    symbol = db.Column(db.String(20), nullable=False, index=True)
    company_name = db.Column(db.String(150), nullable=True)
    transaction_type = db.Column(db.String(10), nullable=False, default='BUY')  # BUY, SELL
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    realized_pnl = db.Column(db.Float, nullable=True, default=0.0)
    status = db.Column(db.String(20), default='COMPLETED', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        """Converts transaction to dictionary."""
        pnl = round(self.realized_pnl, 2) if self.realized_pnl is not None else 0.0
        pnl_str = f"+₹{pnl:,.2f}" if pnl > 0 else (f"-₹{abs(pnl):,.2f}" if pnl < 0 else "₹0.00")
        return {
            'id': self.id,
            'user_id': self.user_id,
            'symbol': self.symbol,
            'company_name': self.company_name or self.symbol,
            'transaction_type': self.transaction_type,
            'quantity': self.quantity,
            'price': round(self.price, 2),
            'formatted_price': f"₹{self.price:,.2f}",
            'total_amount': round(self.total_amount, 2),
            'formatted_total_amount': f"₹{self.total_amount:,.2f}",
            'realized_pnl': pnl,
            'formatted_realized_pnl': pnl_str,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<Transaction id={self.id} user_id={self.user_id} type={self.transaction_type} {self.symbol} qty={self.quantity} price={self.price} pnl={self.realized_pnl}>'
