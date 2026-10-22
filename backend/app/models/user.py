from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from backend.app.extensions import db

class User(db.Model):
    """User account model."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    watchlist_items = db.relationship('Watchlist', backref='user', cascade='all, delete-orphan', lazy=True)
    recent_views = db.relationship('RecentView', backref='user', cascade='all, delete-orphan', lazy=True)
    wallet = db.relationship('Wallet', backref='user', uselist=False, cascade='all, delete-orphan', lazy=True)
    holdings = db.relationship('Holding', backref='user', cascade='all, delete-orphan', lazy=True)
    transactions = db.relationship('Transaction', backref='user', cascade='all, delete-orphan', lazy=True)

    def set_password(self, password: str):
        """Hashes and stores the user password using pbkdf2."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifies the password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return (self.role or '').strip().lower() == 'admin'

    def is_user(self) -> bool:
        """Check if user is a standard user."""
        return (self.role or '').strip().lower() == 'user'

    @property
    def virtual_cash(self) -> float:
        """Returns the user's virtual paper-trading cash balance."""
        if self.wallet:
            return round(self.wallet.virtual_cash, 2)
        return 10000.0

    def to_dict(self):
        """Converts user object to dictionary."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name or '',
            'role': self.role or 'user',
            'virtual_cash': self.virtual_cash,
            'formatted_virtual_cash': f"₹{self.virtual_cash:,.2f}",
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'watchlist_count': len(self.watchlist_items) if self.watchlist_items else 0
        }

    def __repr__(self):
        return f'<User {self.username}>'
