from backend.app.routes.auth_routes import auth_bp
from backend.app.routes.stock_routes import stock_bp
from backend.app.routes.watchlist_routes import watchlist_bp
from backend.app.routes.user_routes import user_bp
from backend.app.routes.view_routes import view_bp
from backend.app.routes.ml_routes import ml_bp
from backend.app.routes.recommendation_routes import recommendation_bp
from backend.app.routes.chatbot_routes import chatbot_bp

__all__ = ['auth_bp', 'stock_bp', 'watchlist_bp', 'user_bp', 'view_bp', 'ml_bp', 'recommendation_bp', 'chatbot_bp']

