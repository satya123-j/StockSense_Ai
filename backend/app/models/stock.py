from datetime import datetime
from backend.app.extensions import db

class StockMetadata(db.Model):
    """Cached stock metadata for fast search and display."""
    __tablename__ = 'stocks_metadata'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    symbol = db.Column(db.String(20), unique=True, nullable=False, index=True)
    company_name = db.Column(db.String(150), nullable=False, index=True)
    exchange = db.Column(db.String(10), default='NSE', nullable=False)
    sector = db.Column(db.String(100), nullable=True)
    industry = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'symbol': self.symbol,
            'company_name': self.company_name,
            'exchange': self.exchange,
            'sector': self.sector or 'N/A',
            'industry': self.industry or 'N/A'
        }


class RecentView(db.Model):
    """Tracks recently viewed stocks per user."""
    __tablename__ = 'recent_views'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    symbol = db.Column(db.String(20), nullable=False)
    company_name = db.Column(db.String(150), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint on user and symbol to allow updating viewed_at
    __table_args__ = (
        db.UniqueConstraint('user_id', 'symbol', name='uq_user_recent_symbol'),
    )

    def to_dict(self):
        return {
            'symbol': self.symbol,
            'company_name': self.company_name,
            'viewed_at': self.viewed_at.isoformat() if self.viewed_at else None
        }
