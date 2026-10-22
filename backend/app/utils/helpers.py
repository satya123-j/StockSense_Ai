from flask import jsonify

def success_response(data=None, message="Success", status_code=200):
    """Formats standard success JSON response."""
    payload = {
        'status': 'success',
        'message': message,
        'data': data
    }
    return jsonify(payload), status_code


def error_response(message="An error occurred", errors=None, status_code=400):
    """Formats standard error JSON response."""
    payload = {
        'status': 'error',
        'message': message,
        'errors': errors
    }
    return jsonify(payload), status_code


def format_currency_inr(value):
    """Formats numeric value into Indian rupee format (Lakhs/Crores)."""
    if value is None:
        return 'N/A'
    try:
        val = float(value)
        if abs(val) >= 1e7:
            return f"₹{val / 1e7:.2f} Cr"
        elif abs(val) >= 1e5:
            return f"₹{val / 1e5:.2f} L"
        else:
            return f"₹{val:,.2f}"
    except (ValueError, TypeError):
        return 'N/A'


def round_num(value, decimals=2):
    """Safely rounds a number or returns None/N/A."""
    if value is None:
        return None
    try:
        val = float(value)
        return round(val, decimals)
    except (ValueError, TypeError):
        return None
