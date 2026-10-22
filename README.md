# StockSense AI — Indian Stock Analysis & Decision-Support Platform

**StockSense AI** is a full-stack, web-based Indian stock analysis and decision-support platform designed for individual investors and traders. It enables users to search Indian NSE/BSE stocks, analyze live quotes and key valuation ratios, visualize multi-timeframe interactive price charts, compute quantitative technical indicators (Moving Averages, RSI, MACD, Bollinger Bands), and maintain a personalized watchlist.

---

## 🏛️ System Architecture

```
Frontend (HTML5 / CSS3 / JavaScript / Bootstrap 5 / Chart.js)
                           ↓ (HTTP REST API / JSON)
                Flask REST API & Route Blueprints
                           ↓
      Auth & Decorator Layer (@token_required / JWT & Session)
                           ↓
                   Business Services Layer
      ├── StockService (Quotes, Search Universe, Live Indices)
      ├── TechnicalAnalysisService (pandas & numpy computations)
      ├── WatchlistService (CRUD & Real-Time Price Enrichment)
      └── AuthService (Registration, Hashing, Token Issuance)
                           ↓
            SQLAlchemy ORM Database Layer
                           ↓
             MySQL Database (or SQLite Fallback)
```

---

## 📂 Project Structure

```
STOCKSENSE_AI/
├── backend/
│   └── app/
│       ├── __init__.py          # Flask Application Factory & Blueprints Registration
│       ├── config.py            # Environment-driven configuration (MySQL/SQLite, JWT, Cache)
│       ├── extensions.py        # SQLAlchemy & Flask-CORS instances
│       ├── models/              # SQLAlchemy Database Models
│       │   ├── __init__.py
│       │   ├── user.py          # User Model & Password Hashing (pbkdf2:sha256)
│       │   ├── watchlist.py     # Watchlist Model (User FK, unique ticker constraint)
│       │   └── stock.py         # StockMetadata & RecentView Models
│       ├── routes/              # Flask Blueprints & REST API Endpoints
│       │   ├── __init__.py
│       │   ├── auth_routes.py   # /api/auth (register, login, logout, me)
│       │   ├── stock_routes.py  # /api/stocks, /api/market/indices
│       │   ├── watchlist_routes.py # /api/watchlist (GET, POST, DELETE)
│       │   ├── user_routes.py   # /api/user (profile, change-password, recent-views)
│       │   └── view_routes.py   # HTML template rendering routes
│       ├── services/            # Core Business Logic Layer
│       │   ├── __init__.py
│       │   ├── auth_service.py              # User authentication & token generation
│       │   ├── stock_service.py             # yfinance fetcher & Indian stock universe
│       │   ├── technical_analysis_service.py # pandas & numpy technical indicator calculations
│       │   └── watchlist_service.py         # Watchlist management & price enrichment
│       └── utils/               # Helpers, Decorators & Input Validators
│           ├── __init__.py
│           ├── decorators.py    # @token_required (JWT Bearer & Cookie validation)
│           ├── helpers.py       # Standardized JSON response formatters & currency helpers
│           └── validators.py    # Email, password strength & ticker sanitizers
├── frontend/
│   ├── static/
│   │   ├── css/
│   │   │   ├── style.css        # Modern fintech dark theme & layout styles
│   │   │   └── components.css   # Cards, tables, badges, toast alerts, skeleton loaders
│   │   └── js/
│   │       ├── api.js           # Fetch API client with JWT interceptor & toast engine
│   │       ├── auth.js          # Client auth state, login/registration handler
│   │       ├── dashboard.js     # Live market indices, autocomplete search, previews
│   │       ├── stock_analysis.js# Chart.js engine with timeframe & indicator overlays
│   │       ├── watchlist.js     # Watchlist manager with real-time price updates
│   │       └── profile.js       # Profile & security settings manager
│   └── templates/
│       ├── base.html            # Master layout with responsive sidebar & top header
│       ├── login.html           # Login page with demo account auto-fill helper
│       ├── register.html        # User sign-up page with real-time validation
│       ├── dashboard.html       # Market dashboard with NIFTY/SENSEX & trending equities
│       ├── stock_analysis.html  # Interactive price charts, RSI, MACD & technical signals
│       ├── watchlist.html       # Watchlist table with live gainers/losers metrics
│       └── profile.html         # User profile and password management
├── tests/
│   └── test_api.py              # Automated unit and API integration tests
├── .env.example                 # Template for environment variables
├── .env                         # Local environment settings
├── init_db.py                   # Database initialization and stock metadata seeding
├── requirements.txt             # Python dependencies
├── run.py                       # Application launcher
└── README.md                    # Comprehensive documentation
```

---

## 🛠️ Technology Stack

- **Backend**: Python 3.10+, Flask, Flask-SQLAlchemy, Flask-CORS, PyJWT, Werkzeug.
- **Data Analysis**: `pandas`, `numpy`, `yfinance`.
- **Database**: MySQL (Production/Standard) / SQLite (Local testing fallback via `.env`).
- **Frontend**: HTML5, CSS3, Vanilla JavaScript (ES6+), Bootstrap 5, Chart.js 4.

---

## ⚡ Installation & Setup Guide

### 1. Prerequisites
- Python 3.10 or higher installed.
- MySQL Server (optional for MySQL mode; SQLite works out-of-the-box).

### 2. Clone / Open Project
```bash
cd STOCKSENSE_AI
```

### 3. Set Up Python Virtual Environment (Recommended)
```bash
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate
```

### 4. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

---

## 🗄️ MySQL Database Configuration

### Step 1: Create the MySQL Database
Open your MySQL client or CLI (`mysql -u root -p`) and create the database:
```sql
CREATE DATABASE stocksense_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Step 2: Configure Environment Variables (`.env`)
Open `.env` in the root folder and configure your MySQL credentials:
```env
# Set USE_SQLITE to False to use MySQL
USE_SQLITE=False

# MySQL Connection Details
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DB=stocksense_ai

# Upstox Developer API v2 (Optional - For Direct Upstox Streaming)
UPSTOX_CLIENT_ID=your_client_id
UPSTOX_CLIENT_SECRET=your_client_secret
UPSTOX_ACCESS_TOKEN=your_access_token
UPSTOX_REDIRECT_URI=http://localhost:5000/api/stocks/upstox/callback

# Alternatively provide direct DATABASE_URL:
# DATABASE_URL=mysql+pymysql://root:your_mysql_password@localhost:3306/stocksense_ai
```

*(Note: If `USE_SQLITE=True`, the app automatically uses `stocksense.db` locally without requiring a running MySQL server).*

### Step 3: Initialize and Seed the Database
Run the database migration and seeder script:
```bash
python init_db.py
```
This will:
1. Create all tables: `users`, `watchlist`, `stocks_metadata`, `recent_views`.
2. Seed 49+ top Indian stocks (NIFTY 50 universe).
3. Create a starter demo account (`demo_user` / `password123`).

---

## 🚀 Running the Web Application

Start the Flask development server:
```bash
python run.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5000
```

### Default Demo Account:
- **Username**: `demo_user`
- **Password**: `password123`
*(Or click the "Auto-Fill" button on the Login page to test immediately)*

---

## 🧪 Running Automated Tests

Run the full API and unit test suite:
```bash
python -m unittest tests/test_api.py
```

---

## 🔐 How Authentication Works

1. **Password Hashing**: User passwords are securely hashed using `pbkdf2:sha256` via Werkzeug security. Plaintext passwords are never stored in the database.
2. **JWT Issuance**: Upon successful login or registration, the backend signs a JSON Web Token (JWT) with HS256 containing `user_id` and an expiration timestamp (default: 7 days).
3. **Session & Token Storage**:
   - The token is saved in the browser's `localStorage` and sent in the `Authorization: Bearer <token>` header with every API request.
   - For web views, a secure cookie and Flask server-side session are also maintained.
4. **Route Protection**: The `@token_required` decorator intercepts incoming requests, verifies the JWT signature and expiration, retrieves the user from the database, and injects `current_user` into the endpoint. Invalid or missing tokens return `401 Unauthorized`.

---

