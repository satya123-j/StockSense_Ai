from datetime import datetime
from backend.app.extensions import db
from backend.app.models.wallet import Wallet
from backend.app.models.user import User

DEFAULT_INITIAL_VIRTUAL_CASH = 10000.0

class WalletService:
    """Service handling virtual paper-trading wallet operations."""

    @staticmethod
    def get_or_create_wallet(user_id: int) -> Wallet:
        """
        Retrieves user's wallet. If the wallet does not yet exist
        (e.g. for existing users created prior to the wallet system),
        safely initializes a new wallet with ₹10,000 virtual cash.
        """
        wallet = Wallet.query.filter_by(user_id=user_id).first()
        if not wallet:
            wallet = Wallet(
                user_id=user_id,
                virtual_cash=DEFAULT_INITIAL_VIRTUAL_CASH,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(wallet)
            db.session.commit()
        return wallet

    @staticmethod
    def get_balance(user_id: int) -> float:
        """Returns the virtual cash balance for a given user."""
        wallet = WalletService.get_or_create_wallet(user_id)
        return round(wallet.virtual_cash, 2)

    @staticmethod
    def update_balance(user_id: int, new_balance: float) -> tuple[dict, str, int]:
        """Sets the exact virtual cash balance for a user."""
        try:
            val = float(new_balance)
        except (ValueError, TypeError):
            return None, "Invalid balance amount specified.", 400

        if val < 0:
            return None, "Virtual cash balance cannot be negative.", 400

        wallet = WalletService.get_or_create_wallet(user_id)
        wallet.virtual_cash = round(val, 2)
        wallet.updated_at = datetime.utcnow()
        db.session.commit()

        return wallet.to_dict(), "Virtual wallet balance updated successfully.", 200

    @staticmethod
    def adjust_balance(user_id: int, delta_amount: float) -> tuple[dict, str, int]:
        """
        Adjusts virtual cash balance by delta_amount (positive to add, negative to deduct).
        Ensures balance does not fall below zero.
        """
        try:
            delta = float(delta_amount)
        except (ValueError, TypeError):
            return None, "Invalid adjustment amount specified.", 400

        wallet = WalletService.get_or_create_wallet(user_id)
        new_total = round(wallet.virtual_cash + delta, 2)

        if new_total < 0:
            return None, f"Insufficient virtual funds. Current balance is ₹{wallet.virtual_cash:,.2f}.", 400

        wallet.virtual_cash = new_total
        wallet.updated_at = datetime.utcnow()
        db.session.commit()

        return wallet.to_dict(), "Virtual cash adjusted successfully.", 200

    @staticmethod
    def admin_modify_balance(target_user_id: int, amount: float = None, set_balance: float = None, reason: str = None, admin_id: int = None) -> tuple[dict, str, int]:
        """
        Administrative function allowing authorized admins to modify individual user's virtual balance.
        Supports either an incremental amount adjustment or setting an explicit balance.
        Records every administrative change into AdminAuditLog.
        """
        from backend.app.models.audit import AdminAuditLog

        target_user = db.session.get(User, target_user_id)
        if not target_user:
            return None, f"Target user with ID {target_user_id} not found.", 404

        wallet = WalletService.get_or_create_wallet(target_user_id)
        old_balance = wallet.virtual_cash

        if set_balance is not None:
            try:
                new_bal = float(set_balance)
            except (ValueError, TypeError):
                return None, "Invalid 'set_balance' numerical amount.", 400

            if new_bal < 0:
                return None, "Virtual balance cannot be negative.", 400

            delta = round(new_bal - old_balance, 2)
            wallet.virtual_cash = round(new_bal, 2)
            action_desc = f"set to ₹{wallet.virtual_cash:,.2f}"

        elif amount is not None:
            try:
                delta = float(amount)
            except (ValueError, TypeError):
                return None, "Invalid 'amount' numerical adjustment.", 400

            if delta <= 0 and set_balance is None:
                # If adding money specifically, amount should be positive
                pass

            new_bal = round(wallet.virtual_cash + delta, 2)
            if new_bal < 0:
                return None, f"Adjustment would result in negative balance. Current: ₹{wallet.virtual_cash:,.2f}.", 400

            wallet.virtual_cash = new_bal
            action_desc = f"credited by +₹{delta:,.2f} (New balance: ₹{wallet.virtual_cash:,.2f})"

        else:
            return None, "Either 'amount' (for adjustment) or 'set_balance' must be provided.", 400

        wallet.updated_at = datetime.utcnow()

        # Record admin audit log
        audit = AdminAuditLog(
            admin_id=admin_id,
            user_id=target_user_id,
            action_type='ADD_VIRTUAL_CASH' if delta >= 0 else 'DEDUCT_VIRTUAL_CASH',
            amount=abs(delta),
            description=f"Admin {action_desc} for user '{target_user.username}'. Reason: {reason or 'Administrative grant'}",
            created_at=datetime.utcnow()
        )
        db.session.add(audit)

        db.session.commit()

        return {
            'wallet': wallet.to_dict(),
            'user': {
                'id': target_user.id,
                'username': target_user.username,
                'email': target_user.email,
                'virtual_cash': wallet.virtual_cash,
                'formatted_virtual_cash': f"₹{wallet.virtual_cash:,.2f}"
            },
            'old_balance': old_balance,
            'new_balance': wallet.virtual_cash,
            'added_amount': delta,
            'audit': audit.to_dict(),
            'reason': reason or 'Admin adjustment'
        }, f"User '{target_user.username}' virtual balance successfully {action_desc}.", 200
