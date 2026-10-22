import re

def validate_email(email: str) -> bool:
    """Validates email format."""
    if not email or not isinstance(email, str):
        return False
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(pattern, email.strip()))


def validate_password(password: str) -> tuple[bool, str]:
    """
    Validates password strength.
    Requires at least 6 characters.
    """
    if not password or not isinstance(password, str):
        return False, "Password is required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
    return True, "Password is valid."


def validate_username(username: str) -> tuple[bool, str]:
    """Validates username requirements."""
    if not username or not isinstance(username, str):
        return False, "Username is required."
    username = username.strip()
    if len(username) < 3 or len(username) > 30:
        return False, "Username must be between 3 and 30 characters."
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain alphanumeric characters and underscores."
    return True, "Username is valid."


def sanitize_stock_symbol(symbol: str) -> str:
    """
    Standardizes stock symbol.
    If no exchange suffix is provided, appends .NS by default for Indian market.
    """
    if not symbol:
        return ''
    symbol = symbol.strip().upper()
    if not (symbol.endswith('.NS') or symbol.endswith('.BO') or symbol.startswith('^')):
        symbol = f"{symbol}.NS"
    return symbol
