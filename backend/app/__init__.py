import os
from flask import Flask, jsonify, render_template
from backend.app.config import config_by_name
from backend.app.extensions import db, cors

def create_app(config_name=None):
    """
    Application factory for StockSense AI.
    Configures extensions, templates, static directories, blueprints, and error handlers.
    """
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    # ========================================================================
    # 1. Template & Static Asset Directory Resolution
    # ========================================================================
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    template_dir = os.path.join(base_dir, 'frontend', 'templates')
    static_dir = os.path.join(base_dir, 'frontend', 'static')

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir,
        static_url_path='/static'
    )

    # ========================================================================
    # 2. Configuration & Extensions Initialization (Database & CORS)
    # ========================================================================
    app_config = config_by_name.get(config_name, config_by_name['default'])
    app.config.from_object(app_config)

    db.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # ========================================================================
    # 3. Blueprint Routing Registration (10 Modular Blueprints)
    # ========================================================================
    from backend.app.routes.auth_routes import auth_bp
    from backend.app.routes.stock_routes import stock_bp
    from backend.app.routes.watchlist_routes import watchlist_bp
    from backend.app.routes.user_routes import user_bp
    from backend.app.routes.view_routes import view_bp
    from backend.app.routes.ml_routes import ml_bp
    from backend.app.routes.recommendation_routes import recommendation_bp
    from backend.app.routes.chatbot_routes import chatbot_bp
    from backend.app.routes.admin_routes import admin_bp
    from backend.app.routes.portfolio_routes import portfolio_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(watchlist_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(view_bp)
    app.register_blueprint(ml_bp)
    app.register_blueprint(recommendation_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(portfolio_bp)

    # ========================================================================
    # 4. Database Table Auto-Creation & Schema Verification
    # ========================================================================
    with app.app_context():
        from backend.app.models.user import User
        from backend.app.models.watchlist import Watchlist
        from backend.app.models.stock import StockMetadata, RecentView
        from backend.app.models.wallet import Wallet
        from backend.app.models.portfolio import Holding, Transaction
        try:
            db.create_all()
            # Ensure 'role' column exists in existing database
            with db.engine.connect() as conn:
                res = conn.execute(db.text("PRAGMA table_info(users)"))
                cols = [r[1] for r in res.fetchall()]
                if 'role' not in cols:
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))
                    conn.commit()

                # Ensure 'realized_pnl' exists in transactions table
                res_tx = conn.execute(db.text("PRAGMA table_info(transactions)"))
                cols_tx = [r[1] for r in res_tx.fetchall()]
                if cols_tx and 'realized_pnl' not in cols_tx:
                    conn.execute(db.text("ALTER TABLE transactions ADD COLUMN realized_pnl FLOAT DEFAULT 0.0"))
                    conn.commit()

            # Ensure all existing users safely have an initialized virtual wallet
            users = User.query.all()
            for u in users:
                if not u.wallet:
                    w = Wallet(user_id=u.id, virtual_cash=10000.0)
                    db.session.add(w)
            db.session.commit()
        except Exception as e:
            print(f"[Warning] Database table auto-creation error: {e}")

    # ========================================================================
    # 5. Global HTTP Error Handlers
    # ========================================================================
    @app.errorhandler(404)
    def handle_404(e):
        if app.template_folder and os.path.exists(os.path.join(template_dir, 'base.html')):
            return jsonify({'status': 'error', 'message': 'Resource not found', 'code': 404}), 404
        return jsonify({'status': 'error', 'message': 'Not Found'}), 404

    @app.errorhandler(500)
    def handle_500(e):
        return jsonify({'status': 'error', 'message': 'Internal server error occurred', 'code': 500}), 500

    return app
