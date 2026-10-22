"""
StockSense AI - Administrative Account Creation CLI
Allows administrators to safely provision the initial admin account
or promote an existing user to the 'admin' role.
"""

import sys
import os
import argparse
import getpass

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.app import create_app
from backend.app.extensions import db
from backend.app.models.user import User
from backend.app.utils.validators import validate_email, validate_username, validate_password


def create_or_promote_admin(username: str, email: str, password: str = None, full_name: str = "System Administrator"):
    """
    Safely creates a new admin user or elevates an existing user to admin.
    """
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    with app.app_context():
        username = username.strip().lower()
        email = email.strip().lower()

        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            print(f"[FOUND] Existing user account detected: '{existing_user.username}' ({existing_user.email})")
            if existing_user.role == 'admin':
                print(f"[INFO] User '{existing_user.username}' is already an Administrator.")
                if password:
                    existing_user.set_password(password)
                    db.session.commit()
                    print(f"[SUCCESS] Password for admin user '{existing_user.username}' was updated.")
                return existing_user

            # Promote to admin
            existing_user.role = 'admin'
            if password:
                existing_user.set_password(password)
            db.session.commit()
            print(f"[SUCCESS] User '{existing_user.username}' successfully promoted to 'admin' role.")
            return existing_user

        # Create new admin user
        # Validate inputs
        u_valid, u_msg = validate_username(username)
        if not u_valid:
            print(f"[ERROR] Invalid username: {u_msg}")
            sys.exit(1)

        if not validate_email(email):
            print("[ERROR] Invalid email address format.")
            sys.exit(1)

        if not password:
            print("[ERROR] Password is required to create a new admin account.")
            sys.exit(1)

        p_valid, p_msg = validate_password(password)
        if not p_valid:
            print(f"[ERROR] Invalid password: {p_msg}")
            sys.exit(1)

        admin_user = User(
            username=username,
            email=email,
            full_name=full_name,
            role='admin'
        )
        admin_user.set_password(password)

        db.session.add(admin_user)
        db.session.commit()

        print("=" * 60)
        print("[SUCCESS] First Administrator account created successfully!")
        print(f"  Username  : {admin_user.username}")
        print(f"  Email     : {admin_user.email}")
        print(f"  Role      : {admin_user.role}")
        print(f"  Full Name : {admin_user.full_name}")
        print("=" * 60)
        return admin_user


def main():
    parser = argparse.ArgumentParser(description="Create or promote an Admin account for StockSense AI.")
    parser.add_argument('--username', help="Admin username")
    parser.add_argument('--email', help="Admin email address")
    parser.add_argument('--password', help="Admin password (optional; will prompt securely if omitted)")
    parser.add_argument('--fullname', default="System Administrator", help="Admin display name")

    args = parser.parse_args()

    username = args.username
    email = args.email
    password = args.password
    fullname = args.fullname

    # Interactive mode if arguments are omitted
    if not username:
        print("\n--- StockSense AI Admin Account Setup ---")
        username = input("Enter admin username [e.g. admin]: ").strip() or "admin"

    if not email:
        email = input("Enter admin email [e.g. admin@stocksense.ai]: ").strip() or "admin@stocksense.ai"

    if not password:
        password = getpass.getpass("Enter secure admin password: ")
        confirm_password = getpass.getpass("Confirm admin password: ")
        if password != confirm_password:
            print("[ERROR] Passwords do not match.")
            sys.exit(1)

    create_or_promote_admin(username, email, password, fullname)


if __name__ == '__main__':
    main()
