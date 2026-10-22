import jwt
from datetime import datetime, timedelta
from flask import current_app
from backend.app.extensions import db
from backend.app.models.user import User
from backend.app.models.wallet import Wallet
from backend.app.utils.validators import validate_email, validate_password, validate_username

class AuthService:
    """Service handling authentication and user registration logic."""

    @staticmethod
    def generate_token(user_id, role: str = 'user') -> str:
        """Generates a signed JWT access token for a user with their role claim."""
        if isinstance(user_id, User):
            role = user_id.role or role
            user_id = user_id.id
        elif hasattr(user_id, 'id'):
            role = getattr(user_id, 'role', role)
            user_id = user_id.id

        expires = datetime.utcnow() + current_app.config['JWT_ACCESS_TOKEN_EXPIRES']
        payload = {
            'user_id': user_id,
            'role': role,
            'exp': expires,
            'iat': datetime.utcnow()
        }
        token = jwt.encode(
            payload,
            current_app.config['JWT_SECRET_KEY'],
            algorithm='HS256'
        )
        return token

    @staticmethod
    def register(username: str, email: str, password: str, full_name: str = None, role: str = 'user') -> tuple[dict, str, int]:
        """
        Validates user input and creates a new user account.
        Standard public registrations are always assigned 'user' role.
        Returns (data_dict, error_message, status_code).
        """
        # Validate username
        u_valid, u_msg = validate_username(username)
        if not u_valid:
            return None, u_msg, 400

        # Validate email
        if not validate_email(email):
            return None, "Invalid email address format.", 400

        # Validate password
        p_valid, p_msg = validate_password(password)
        if not p_valid:
            return None, p_msg, 400

        # Check existing username
        if User.query.filter_by(username=username.strip().lower()).first():
            return None, "Username already taken. Please choose another.", 409

        # Check existing email
        if User.query.filter_by(email=email.strip().lower()).first():
            return None, "An account with this email already exists.", 409

        # Public registration creates standard 'user'
        assigned_role = 'user' if role not in ('user', 'admin') else role

        # Create user
        user = User(
            username=username.strip().lower(),
            email=email.strip().lower(),
            full_name=full_name.strip() if full_name else '',
            role=assigned_role
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        # Automatically allocate ₹10,000 simulated virtual cash for paper trading
        wallet = Wallet(user_id=user.id, virtual_cash=10000.0)
        db.session.add(wallet)
        db.session.commit()

        token = AuthService.generate_token(user.id, user.role)
        return {
            'user': user.to_dict(),
            'token': token,
            'redirect_url': '/admin' if user.is_admin() else '/dashboard'
        }, "Registration successful.", 201

    @staticmethod
    def login(identifier: str, password: str, requested_role: str = None) -> tuple[dict, str, int]:
        """
        Authenticates a user via username or email and password,
        verifying permissions against the database-stored role.
        Returns (data_dict, error_message, status_code).
        """
        if not identifier or not password:
            return None, "Username/email and password are required.", 400

        identifier = identifier.strip().lower()
        # Search by username or email
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if not user or not user.check_password(password):
            return None, "Invalid credentials. Please verify your username and password.", 401

        actual_role = (user.role or 'user').strip().lower()

        # Enforce role boundaries when requested from UI
        if requested_role:
            req_role = requested_role.strip().lower()
            if req_role == 'admin' and actual_role != 'admin':
                return None, "Access denied. Administrator privileges required.", 403
            if req_role == 'user' and actual_role == 'admin':
                return None, "Admin accounts cannot log in as standard users. Please use Admin Login.", 403

        token = AuthService.generate_token(user.id, actual_role)
        return {
            'user': user.to_dict(),
            'token': token,
            'redirect_url': '/admin' if actual_role == 'admin' else '/dashboard'
        }, "Login successful.", 200

    @staticmethod
    def change_password(user: User, current_password: str, new_password: str) -> tuple[bool, str, int]:
        """Changes user password after validating the current password."""
        if not user.check_password(current_password):
            return False, "Current password is incorrect.", 400

        p_valid, p_msg = validate_password(new_password)
        if not p_valid:
            return False, p_msg, 400

        user.set_password(new_password)
        db.session.commit()
        return True, "Password updated successfully.", 200

    @staticmethod
    def update_profile(user: User, full_name: str, email: str) -> tuple[dict, str, int]:
        """Updates user profile information."""
        if email and email.strip().lower() != user.email:
            new_email = email.strip().lower()
            if not validate_email(new_email):
                return None, "Invalid email address format.", 400
            # Check if taken
            existing = User.query.filter(User.email == new_email, User.id != user.id).first()
            if existing:
                return None, "Email address is already in use by another account.", 409
            user.email = new_email

        if full_name is not None:
            user.full_name = full_name.strip()

        db.session.commit()
        return user.to_dict(), "Profile updated successfully.", 200
