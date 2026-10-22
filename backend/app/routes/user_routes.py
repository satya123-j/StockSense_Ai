from flask import Blueprint, request
from backend.app.services.auth_service import AuthService
from backend.app.models.stock import RecentView
from backend.app.utils.helpers import success_response, error_response
from backend.app.utils.decorators import token_required

user_bp = Blueprint('user_api', __name__, url_prefix='/api/user')

@user_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    """Retrieve full user profile."""
    return success_response(data=current_user.to_dict())


@user_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    """Update profile information."""
    data = request.get_json() or {}
    full_name = data.get('full_name')
    email = data.get('email')

    updated_user, message, status_code = AuthService.update_profile(current_user, full_name, email)
    if not updated_user:
        return error_response(message=message, status_code=status_code)

    return success_response(data=updated_user, message=message)


@user_bp.route('/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    """Change account password."""
    data = request.get_json() or {}
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return error_response("Both current and new password are required.", status_code=400)

    success, message, status_code = AuthService.change_password(current_user, current_password, new_password)
    if not success:
        return error_response(message=message, status_code=status_code)

    return success_response(message=message)


@user_bp.route('/recent-views', methods=['GET'])
@token_required
def get_recent_views(current_user):
    """Retrieve recently viewed stocks for the authenticated user."""
    views = RecentView.query.filter_by(user_id=current_user.id).order_by(RecentView.viewed_at.desc()).limit(10).all()
    return success_response(data=[v.to_dict() for v in views])


@user_bp.route('/wallet', methods=['GET'])
@token_required
def get_user_wallet(current_user):
    """Retrieve virtual paper-trading wallet balance for the authenticated user."""
    from backend.app.services.wallet_service import WalletService
    wallet = WalletService.get_or_create_wallet(current_user.id)
    return success_response(data=wallet.to_dict(), message="Virtual wallet retrieved.")

