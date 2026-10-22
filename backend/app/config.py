import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'stocksense_ai_default_secret_key_2026')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'stocksense_jwt_secret_key_2026')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES_DAYS', 7)))
    
    # SQLAlchemy configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True
    }
    
    # Upstox API Configuration (Official Developer API v2)
    UPSTOX_CLIENT_ID = os.getenv('UPSTOX_CLIENT_ID', '')
    UPSTOX_CLIENT_SECRET = os.getenv('UPSTOX_CLIENT_SECRET', '')
    UPSTOX_ACCESS_TOKEN = os.getenv('UPSTOX_ACCESS_TOKEN', '')
    UPSTOX_REDIRECT_URI = os.getenv('UPSTOX_REDIRECT_URI', 'http://127.0.0.1:5000/api/auth/upstox/callback')
    UPSTOX_BASE_URL = os.getenv('UPSTOX_BASE_URL', 'https://api.upstox.com/v2')
    UPSTOX_ENABLED = os.getenv('UPSTOX_ENABLED', 'True').lower() in ('true', '1', 't')

    # Cache & fallback settings
    CACHE_EXPIRY_SECONDS = int(os.getenv('CACHE_EXPIRY_SECONDS', 180))
    ENABLE_DEMO_DATA_FALLBACK = os.getenv('ENABLE_DEMO_DATA_FALLBACK', 'True').lower() in ('true', '1', 't')

    # AI Chatbot Configuration
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY', '')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    CHATBOT_PROVIDER = os.getenv('CHATBOT_PROVIDER', 'auto')


    @staticmethod
    def get_database_uri():
        """
        Builds the database URI.
        Supports MySQL by default, with SQLite fallback if USE_SQLITE is True or MySQL credentials not configured.
        """
        use_sqlite = os.getenv('USE_SQLITE', 'False').lower() in ('true', '1', 't')
        database_url = os.getenv('DATABASE_URL')
        
        if use_sqlite:
            # Fallback to local SQLite file
            base_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            db_path = os.path.join(base_dir, 'stocksense.db')
            return f'sqlite:///{db_path}'
            
        if database_url and not database_url.startswith('sqlite'):
            return database_url
            
        # Build MySQL Connection URI
        user = os.getenv('MYSQL_USER', 'root')
        password = os.getenv('MYSQL_PASSWORD', 'rootpassword')
        host = os.getenv('MYSQL_HOST', 'localhost')
        port = os.getenv('MYSQL_PORT', '3306')
        dbname = os.getenv('MYSQL_DB', 'stocksense_ai')
        
        return f'mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}'


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = Config.get_database_uri()


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = Config.get_database_uri()


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Config dictionary mapping
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
