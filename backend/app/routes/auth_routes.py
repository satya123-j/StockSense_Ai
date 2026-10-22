from flask import Blueprint, request, session, make_response, redirect, jsonify
from backend.app.services.auth_service import AuthService
from backend.app.services.upstox_service import UpstoxService
from backend.app.utils.helpers import success_response, error_response
from backend.app.utils.decorators import token_required

auth_bp = Blueprint('auth_api', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user account."""
    data = request.get_json() or {}
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    full_name = data.get('full_name')

    result, message, status_code = AuthService.register(username, email, password, full_name)
    if not result:
        return error_response(message=message, status_code=status_code)

    # Set session for server-side template convenience
    session['user_id'] = result['user']['id']
    session['username'] = result['user']['username']
    session['role'] = result['user'].get('role', 'user')

    resp = make_response(success_response(data=result, message=message, status_code=status_code))
    # Set secure cookie for JWT token
    resp.set_cookie('jwt_token', result['token'], httponly=False, samesite='Lax', max_age=7*24*3600)
    return resp


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user with username/email and password."""
    data = request.get_json() or {}
    identifier = data.get('identifier') or data.get('username') or data.get('email')
    password = data.get('password')
    requested_role = data.get('role')

    result, message, status_code = AuthService.login(identifier, password, requested_role=requested_role)
    if not result:
        return error_response(message=message, status_code=status_code)

    # Save session
    session['user_id'] = result['user']['id']
    session['username'] = result['user']['username']
    session['role'] = result['user'].get('role', 'user')

    resp = make_response(success_response(data=result, message=message, status_code=status_code))
    resp.set_cookie('jwt_token', result['token'], httponly=False, samesite='Lax', max_age=7*24*3600)
    return resp


@auth_bp.route('/logout', methods=['POST', 'GET'])
def logout():
    """Clear session and remove auth cookie."""
    session.clear()
    resp = make_response(success_response(message="Logged out successfully."))
    resp.delete_cookie('jwt_token')
    return resp


@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    """Returns the authenticated user's profile."""
    return success_response(data=current_user.to_dict())


# Upstox Developer OAuth 2.0 Endpoints
@auth_bp.route('/upstox/login', methods=['GET'])
def upstox_login():
    """Generates Upstox OAuth 2.0 login URL and redirects the user."""
    client_id = UpstoxService.get_client_id()
    if not client_id:
        return error_response("UPSTOX_CLIENT_ID is not configured in .env", status_code=503)

    login_url = UpstoxService.get_login_url()
    return redirect(login_url)


@auth_bp.route('/upstox/callback', methods=['GET'])
def upstox_callback():
    """Handles OAuth 2.0 authorization code callback from Upstox."""
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return error_response(f"Upstox authorization error: {error}", status_code=400)

    if not code:
        return error_response("Missing authorization code from Upstox callback.", status_code=400)

    data, message, status_code = UpstoxService.exchange_code_for_token(code)
    if not data:
        return error_response(message=message, status_code=status_code)

    # Return success confirmation
    return success_response(
        data={"access_token_received": True, "token_type": data.get('token_type', 'Bearer')},
        message="Upstox authorization successful. Set this token as UPSTOX_ACCESS_TOKEN in your .env file."
    )
