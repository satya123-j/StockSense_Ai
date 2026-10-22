from flask import Blueprint, render_template, redirect, url_for, session, request
from backend.app.utils.decorators import get_authenticated_user

view_bp = Blueprint('views', __name__)

@view_bp.route('/')
def index():
    """Root route redirecting to dashboard or admin portal based on authenticated role."""
    user = get_authenticated_user()
    if user and user.is_admin():
        return redirect(url_for('admin.admin_dashboard'))
    return redirect(url_for('views.dashboard'))


@view_bp.route('/login')
def login():
    """Renders login view with role selector."""
    user = get_authenticated_user()
    if user:
        return redirect(url_for('admin.admin_dashboard') if user.is_admin() else url_for('views.dashboard'))
    return render_template('login.html', active_page='login')


@view_bp.route('/register')
def register():
    """Renders user registration view."""
    return render_template('register.html', active_page='register')


@view_bp.route('/dashboard')
def dashboard():
    """Renders main stock analysis dashboard for standard users."""
    user = get_authenticated_user()
    if user and user.is_admin():
        return redirect(url_for('admin.admin_dashboard'))
    return render_template('dashboard.html', active_page='dashboard')


@view_bp.route('/analysis')
@view_bp.route('/analysis/<symbol>')
def stock_analysis(symbol=None):
    """Renders in-depth stock technical analysis view."""
    default_symbol = symbol or 'RELIANCE'
    return render_template('stock_analysis.html', active_page='analysis', symbol=default_symbol)


@view_bp.route('/watchlist')
def watchlist():
    """Renders user stock watchlist view."""
    user = get_authenticated_user()
    if user and user.is_admin():
        return redirect(url_for('admin.admin_dashboard'))
    return render_template('watchlist.html', active_page='watchlist')


@view_bp.route('/markets')
def markets():
    """Renders Indian markets overview."""
    return render_template('markets.html', active_page='markets')


@view_bp.route('/portfolio')
def portfolio():
    """Renders user paper trading portfolio view (accessible only to logged-in user)."""
    user = get_authenticated_user()
    if not user:
        return redirect(url_for('views.login', next=request.path))
    if user.is_admin():
        return redirect(url_for('admin.admin_dashboard'))
    return render_template('portfolio.html', active_page='portfolio')


@view_bp.route('/profile')
def profile():
    """Renders user account & profile view."""
    return render_template('profile.html', active_page='profile')

