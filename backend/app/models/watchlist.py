from datetime import datetime
from backend.app.extensions import db

class Watchlist(db.Model):
    """User stock watchlist model."""
    __tablename__ = 'watchlist'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    symbol = db.Column(db.String(20), nullable=False)  # e.g., RELIANCE.NS, TCS.NS
    company_name = db.Column(db.String(150), nullable=False)
    exchange = db.Column(db.String(10), default='NSE', nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)

    # Unique constraint: a user cannot add the same stock twice
    __table_args__ = (
        db.UniqueConstraint('user_id', 'symbol', name='uq_user_symbol'),
    )

    def to_dict(self):
        """Returns dictionary representation of watchlist item."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'symbol': self.symbol,
            'company_name': self.company_name,
            'exchange': self.exchange,
            'added_at': self.added_at.isoformat() if self.added_at else None,
            'notes': self.notes or ''
        }

    def __repr__(self):
        return f'<Watchlist {self.symbol} for User {self.user_id}>'
