from datetime import datetime
from backend.app.extensions import db

class Wallet(db.Model):
    """
    Virtual paper-trading cash wallet model.
    Maintains simulated cash balance for user paper trading.
    Initial balance for new users is ₹10,000.
    """
    __tablename__ = 'wallets'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    virtual_cash = db.Column(db.Float, nullable=False, default=10000.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Converts wallet object to serializable dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'virtual_cash': round(self.virtual_cash, 2),
            'formatted_virtual_cash': f"₹{self.virtual_cash:,.2f}",
            'currency': 'INR',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<Wallet user_id={self.user_id} virtual_cash={self.virtual_cash}>'
