import jwt
from functools import wraps
from flask import request, current_app, session, redirect, url_for, render_template
from backend.app.extensions import db
from backend.app.models.user import User
from backend.app.utils.helpers import error_response


def get_authenticated_user():
    """
    Extracts and verifies the currently authenticated user from Bearer header,
    jwt_token cookie, or Flask session.
    Returns User instance or None.
    """
    token = None
    user = None

    # Check Authorization Header: Bearer <token>
    auth_header = request.headers.get('Authorization')
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            token = parts[1]

    # If no Bearer token, check cookies
    if not token and 'jwt_token' in request.cookies:
        token = request.cookies.get('jwt_token')

    if token:
        try:
            payload = jwt.decode(
                token,
                current_app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )
            user_id = payload.get('user_id')
            if user_id:
                user = db.session.get(User, user_id)
        except Exception:
            user = None

    # Fallback to session if no token or token decode failed
    if not user and 'user_id' in session:
        user = db.session.get(User, session['user_id'])

    return user


def is_json_request():
    """Determines whether the incoming request expects a JSON response."""
    return (
        request.path.startswith('/api/')
        or request.is_json
        or request.headers.get('Accept') == 'application/json'
        or 'application/json' in request.headers.get('Accept', '')
    )


def token_required(f):
    """
    Decorator that requires a valid JWT token in the Authorization header
    or an active user_id in the Flask session.
    Attaches current_user to the wrapped function.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        user = None

        # Check Authorization Header: Bearer <token>
        auth_header = request.headers.get('Authorization')
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]

        # If no Bearer token, check cookies or flask session
        if not token and 'jwt_token' in request.cookies:
            token = request.cookies.get('jwt_token')

        if token:
            try:
                payload = jwt.decode(
                    token,
                    current_app.config['JWT_SECRET_KEY'],
                    algorithms=['HS256']
                )
                user_id = payload.get('user_id')
                user = db.session.get(User, user_id)
            except jwt.ExpiredSignatureError:
                return error_response("Token has expired. Please log in again.", status_code=401)
            except (jwt.InvalidTokenError, Exception):
                return error_response("Invalid authentication token.", status_code=401)

        # Fallback to session if no token or token decode failed
        if not user and 'user_id' in session:
            user = db.session.get(User, session['user_id'])

        if not user:
            return error_response("Authentication required to access this resource.", status_code=401)

        return f(current_user=user, *args, **kwargs)

    return decorated


def admin_required(f):
    """
    Decorator enforcing that the request comes from an authenticated user with ADMIN role.
    Role is strictly verified against the database record.
    - If unauthenticated: returns 401 for API, redirects to /login for HTML views.
    - If authenticated but not admin: returns 403 for API, renders 403.html for HTML views.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_authenticated_user()

        if not user:
            if is_json_request():
                return error_response("Authentication required to access this resource.", status_code=401)
            return redirect(url_for('views.login', next=request.path))

        # Enforce admin role check from database
        if not user.is_admin():
            if is_json_request():
                return error_response("Access forbidden: Administrator privileges required.", status_code=403)
            return render_template('403.html', user=user), 403

        return f(current_user=user, *args, **kwargs)

    return decorated


def user_required(f):
    """
    Decorator enforcing that the request comes from an authenticated standard USER.
    Admin accounts cannot use standard user features (e.g. watchlist, paper trading).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_authenticated_user()

        if not user:
            if is_json_request():
                return error_response("Authentication required to access this resource.", status_code=401)
            return redirect(url_for('views.login', next=request.path))

        # Admin accounts cannot act as normal users
        if not user.is_user():
            if is_json_request():
                return error_response("Access forbidden: Standard user account required. Admin accounts cannot access user portfolio features.", status_code=403)
            return redirect(url_for('admin.admin_dashboard'))

        return f(current_user=user, *args, **kwargs)

    return decorated
