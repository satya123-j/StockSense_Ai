import os
from backend.app import create_app

app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '127.0.0.1')
    debug = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
    
    print("=" * 60)
    print(" [StockSense AI] - Indian Stock Analysis Platform")
    print(f" [Web Dashboard] http://{host}:{port}")
    print("=" * 60)
    
    app.run(host=host, port=port, debug=debug)
