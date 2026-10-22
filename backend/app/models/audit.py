from datetime import datetime
from backend.app.extensions import db

class AdminAuditLog(db.Model):
    """
    Audit log model recording administrative actions and capital adjustments.
    """
    __tablename__ = 'admin_audit_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    action_type = db.Column(db.String(50), nullable=False, default='ADD_VIRTUAL_CASH')
    amount = db.Column(db.Float, nullable=True, default=0.0)
    description = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    admin = db.relationship('User', foreign_keys=[admin_id], backref='admin_actions_logged')
    target_user = db.relationship('User', foreign_keys=[user_id], backref='audit_entries')

    def to_dict(self):
        """Converts audit log to dictionary."""
        amt = round(self.amount, 2) if self.amount is not None else 0.0
        return {
            'id': self.id,
            'admin_id': self.admin_id,
            'admin_username': self.admin.username if self.admin else 'System Admin',
            'user_id': self.user_id,
            'user_username': self.target_user.username if self.target_user else 'Unknown',
            'action_type': self.action_type,
            'amount': amt,
            'formatted_amount': f"₹{amt:,.2f}",
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<AdminAuditLog id={self.id} action={self.action_type} user_id={self.user_id} amount={self.amount}>'
