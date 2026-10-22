from flask import Blueprint, render_template, request
from backend.app.extensions import db
from backend.app.models.user import User
from backend.app.utils.decorators import admin_required
from backend.app.utils.helpers import success_response, error_response

admin_bp = Blueprint('admin', __name__)

# ============================================================================
# 1. Admin Portal View & RBAC Status Verification
# ============================================================================
@admin_bp.route('/admin', methods=['GET'])
@admin_bp.route('/admin/dashboard', methods=['GET'])
@admin_required
def admin_dashboard(current_user):
    """
    Renders the protected Admin Portal landing page.
    Backend authorization strictly validates the admin role.
    """
    return render_template('admin.html', active_page='admin', current_user=current_user)


@admin_bp.route('/api/admin/status', methods=['GET'])
@admin_required
def admin_status(current_user):
    """
    Protected API endpoint to verify administrative authorization.
    Returns 401 if unauthenticated, 403 if authenticated non-admin.
    """
    return success_response(
        data={
            'role': current_user.role,
            'user_id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'access_level': 'administrator',
            'authorized': True
        },
        message="Administrative authorization verified successfully."
    )


from backend.app.services.paper_trading_service import PaperTradingService
from backend.app.services.wallet_service import WalletService
from backend.app.models.portfolio import Transaction
from backend.app.models.audit import AdminAuditLog


# ============================================================================
# 2. User Directory & Metrics Overview
# ============================================================================
@admin_bp.route('/api/admin/users', methods=['GET'])
@admin_required
def get_all_users(current_user):
    """
    Protected administrative route retrieving platform user accounts and metrics:
    - User ID
    - Name
    - Email
    - Registration Date
    - Role
    - Virtual Cash
    - Portfolio Value
    - Total P/L
    Passwords are never exposed.
    """
    users = User.query.order_by(User.id.asc()).all()
    user_list = []

    for u in users:
        try:
            summary = PaperTradingService.get_portfolio_summary(u.id)
        except Exception:
            wallet = WalletService.get_or_create_wallet(u.id)
            summary = {
                'virtual_cash': wallet.virtual_cash,
                'formatted_virtual_cash': f"₹{wallet.virtual_cash:,.2f}",
                'current_portfolio_value': 0.0,
                'formatted_current_portfolio_value': "₹0.00",
                'total_investment': 0.0,
                'total_portfolio_value': wallet.virtual_cash,
                'total_pnl': 0.0,
                'formatted_total_pnl': "₹0.00",
                'total_pnl_percent': 0.0,
                'formatted_total_pnl_percent': "0.00%",
                'is_profit': True,
                'holdings_count': 0
            }

        user_list.append({
            'id': u.id,
            'name': u.full_name or u.username,
            'username': u.username,
            'email': u.email,
            'registration_date': u.created_at.strftime('%d %b %Y') if u.created_at else 'N/A',
            'created_at': u.created_at.isoformat() if u.created_at else None,
            'role': u.role or 'user',
            'virtual_cash': summary['virtual_cash'],
            'formatted_virtual_cash': summary['formatted_virtual_cash'],
            'portfolio_value': summary.get('current_portfolio_value', 0.0),
            'formatted_portfolio_value': summary.get('formatted_current_portfolio_value', '₹0.00'),
            'total_investment': summary.get('total_investment', 0.0),
            'total_portfolio_value': summary.get('total_portfolio_value', summary['virtual_cash']),
            'total_pnl': summary.get('total_pnl', 0.0),
            'formatted_total_pnl': summary.get('formatted_total_pnl', '₹0.00'),
            'total_pnl_percent': summary.get('total_pnl_percent', 0.0),
            'formatted_total_pnl_percent': summary.get('formatted_total_pnl_percent', '0.00%'),
            'is_profit': summary.get('is_profit', True),
            'holdings_count': summary.get('holdings_count', 0)
        })

    return success_response(
        data=user_list,
        message="System user directory retrieved for administrative inspection."
    )


# ============================================================================
# 3. Individual User Account & Portfolio Inspection
# ============================================================================
@admin_bp.route('/api/admin/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user_details(current_user, user_id):
    """
    Returns complete user details for a selected user:
    - User information
    - Virtual cash
    - Portfolio holdings
    - Current portfolio value
    - Total P/L
    - Transaction history
    - Audit history
    """
    target_user = db.session.get(User, user_id)
    if not target_user:
        return error_response(f"User with ID {user_id} not found.", status_code=404)

    try:
        summary = PaperTradingService.get_portfolio_summary(user_id)
    except Exception:
        wallet = WalletService.get_or_create_wallet(user_id)
        summary = {
            'virtual_cash': wallet.virtual_cash,
            'formatted_virtual_cash': f"₹{wallet.virtual_cash:,.2f}",
            'current_portfolio_value': 0.0,
            'formatted_current_portfolio_value': "₹0.00",
            'total_investment': 0.0,
            'formatted_total_investment': "₹0.00",
            'total_portfolio_value': wallet.virtual_cash,
            'formatted_total_portfolio_value': f"₹{wallet.virtual_cash:,.2f}",
            'total_pnl': 0.0,
            'formatted_total_pnl': "₹0.00",
            'total_pnl_percent': 0.0,
            'formatted_total_pnl_percent': "0.00%",
            'is_profit': True,
            'holdings': []
        }
    transactions = PaperTradingService.get_user_transactions(user_id)
    audits = AdminAuditLog.query.filter_by(user_id=user_id).order_by(AdminAuditLog.created_at.desc()).all()

    return success_response(
        data={
            'user': {
                'id': target_user.id,
                'name': target_user.full_name or target_user.username,
                'username': target_user.username,
                'email': target_user.email,
                'role': target_user.role or 'user',
                'created_at': target_user.created_at.isoformat() if target_user.created_at else None,
                'registration_date': target_user.created_at.strftime('%d %b %Y') if target_user.created_at else 'N/A'
            },
            'virtual_cash': summary['virtual_cash'],
            'formatted_virtual_cash': summary['formatted_virtual_cash'],
            'portfolio_value': summary['current_portfolio_value'],
            'formatted_portfolio_value': summary['formatted_current_portfolio_value'],
            'total_investment': summary['total_investment'],
            'formatted_total_investment': summary['formatted_total_investment'],
            'total_portfolio_value': summary['total_portfolio_value'],
            'formatted_total_portfolio_value': summary['formatted_total_portfolio_value'],
            'total_pnl': summary['total_pnl'],
            'formatted_total_pnl': summary['formatted_total_pnl'],
            'total_pnl_percent': summary['total_pnl_percent'],
            'formatted_total_pnl_percent': summary['formatted_total_pnl_percent'],
            'is_profit': summary['is_profit'],
            'holdings': summary['holdings'],
            'holdings_count': len(summary['holdings']),
            'transactions': transactions,
            'transactions_count': len(transactions),
            'audit_logs': [a.to_dict() for a in audits]
        },
        message=f"Detailed profile for '{target_user.username}' retrieved."
    )


# ============================================================================
# 4. System-Wide Paper-Trading Activity Stream
# ============================================================================
@admin_bp.route('/api/admin/activity', methods=['GET'])
@admin_required
def get_user_activity(current_user):
    """
    Returns platform-wide paper-trading activity:
    - BUY
    - SELL
    - Stock
    - Quantity
    - Price
    - Amount
    - Date/Time
    - User details (ID, username)
    """
    # Query transactions with associated user details
    txs = Transaction.query.order_by(Transaction.created_at.desc()).limit(150).all()
    activity_list = []

    for t in txs:
        u = db.session.get(User, t.user_id)
        activity_list.append({
            'id': t.id,
            'user_id': t.user_id,
            'username': u.username if u else 'Unknown',
            'user_name': (u.full_name or u.username) if u else 'Unknown',
            'symbol': t.symbol,
            'company_name': t.company_name or t.symbol,
            'action': t.transaction_type,  # BUY or SELL
            'transaction_type': t.transaction_type,
            'quantity': t.quantity,
            'price': round(t.price, 2),
            'formatted_price': f"₹{t.price:,.2f}",
            'total_amount': round(t.total_amount, 2),
            'formatted_total_amount': f"₹{t.total_amount:,.2f}",
            'realized_pnl': t.realized_pnl,
            'status': t.status,
            'created_at': t.created_at.isoformat() if t.created_at else None,
            'formatted_date': t.created_at.strftime('%d %b %Y, %I:%M %p') if t.created_at else 'N/A'
        })

    return success_response(
        data=activity_list,
        message="System-wide paper-trading activity stream retrieved."
    )


# ============================================================================
# 5. Virtual Cash Management & Administrative Credit/Debit
# ============================================================================
@admin_bp.route('/api/admin/users/<int:user_id>/add-money', methods=['POST'])
@admin_bp.route('/api/admin/users/<int:user_id>/wallet', methods=['POST', 'PUT'])
@admin_required
def admin_add_virtual_money(current_user, user_id):
    """
    Administrative endpoint allowing authorized admins to add virtual money to a user's wallet.
    Example:
      Current: ₹4,000 + Added: ₹5,000 = New balance: ₹9,000
    Backend performs calculation and records action into AdminAuditLog.
    """
    data = request.get_json() or {}
    amount = data.get('amount')
    reason = data.get('reason') or 'Administrative grant'
    set_balance = data.get('set_balance')

    # Validation: amount must be positive if specified
    if amount is not None:
        try:
            amt = float(amount)
            if amt <= 0:
                return error_response("Amount to add must be a positive number greater than zero.", status_code=400)
        except (ValueError, TypeError):
            return error_response("Invalid amount format. Must be a numeric value.", status_code=400)
    elif set_balance is None:
        return error_response("Amount to add is required.", status_code=400)

    result, message, status_code = WalletService.admin_modify_balance(
        target_user_id=user_id,
        amount=amount,
        set_balance=set_balance,
        reason=reason,
        admin_id=current_user.id
    )

    if not result:
        return error_response(message=message, status_code=status_code)

    return success_response(data=result, message=message, status_code=status_code)


# ============================================================================
# 6. Administrative Audit Trail Logs
# ============================================================================
@admin_bp.route('/api/admin/audit-logs', methods=['GET'])
@admin_required
def get_audit_logs(current_user):
    """Returns platform administrative audit log history."""
    logs = AdminAuditLog.query.order_by(AdminAuditLog.created_at.desc()).limit(100).all()
    return success_response(
        data=[log.to_dict() for log in logs],
        message="Audit logs retrieved successfully."
    )


