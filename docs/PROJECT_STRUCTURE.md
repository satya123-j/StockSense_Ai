# StockSense AI — Project Architecture & Execution Flow

This document outlines the architecture, end-to-end execution flow, folder hierarchy, and design of the **StockSense AI** Indian Stock Analysis & Paper Trading Platform.

---

## 1. High-Level Architecture & Execution Flow

```text
       ┌────────────────────────────────────────────────────────┐
       │                 User Opens Web Browser                 │
       │             (http://127.0.0.1:5000)                    │
       └───────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │                        FRONTEND                        │
       │   HTML5 (Jinja2 Templates) + Vanilla CSS + JavaScript  │
       │   - Interactive Chart.js candlesticks & indicators     │
       │   - AI Chatbot sliding drawer & prompt chips           │
       │   - Paper Trading order modals & portfolio dashboard   │
       └───────────────────────────┬────────────────────────────┘
                                   │  HTTP / REST JSON Requests
                                   │  (Session Cookie / JWT Bearer)
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │                     FLASK BACKEND                      │
       │      Application Entry (run.py & create_app)           │
       │   - Request routing via 10 modular Flask Blueprints    │
       │   - Role-Based Access Control (@admin_required)        │
       │   - Input sanitization, validation, and error handlers │
       └───────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │                     BUSINESS LOGIC                     │
       │              Python Services & ML Engines              │
       │   - Technical Analysis: RSI, MACD, SMA20, SMA50        │
       │   - ML Forecasting: Scikit-learn Linear Regression     │
       │     and Random Forest Regressor                        │
       │   - AI Recommendation: Multi-factor scoring (-100..+100)│
       │   - AI Chatbot: Context normalization + LLM reasoning  │
       │   - Paper Trading: Wallet balance & order execution    │
       └──────────────┬──────────────────────────┬──────────────┘
                      │                          │
       Query / Update │                          │ Live Market Data /
       Local Records  │                          │ Upstox API v2 / yfinance
                      ▼                          ▼
       ┌────────────────────────┐      ┌────────────────────────┐
       │   DATABASE (SQLite)    │      │  EXTERNAL STOCK APIS   │
       │     stocksense.db      │      │  - Upstox Developer v2 │
       │  - Users & Roles       │      │  - yfinance (NSE .NS)  │
       │  - Wallets (Cash)      │      │  - Google Gemini API / │
       │  - Holdings & Orders   │      │    OpenAI (LLM Chat)   │
       │  - Admin Audit Logs    │      │                        │
       └──────────────┬─────────┘      └────────────┬───────────┘
                      │                             │
                      └──────────────┬──────────────┘
                                     │
                                     ▼
       ┌────────────────────────────────────────────────────────┐
       │               RESULTS RETURNED TO FRONTEND             │
       │  - Clean JSON payloads rendered dynamically via JS     │
       │  - Real-time chart updates, indicator values, badges   │
       └────────────────────────────────────────────────────────┘
```

> **Note on ML & AI Execution:**
> In StockSense AI, Machine Learning (Scikit-learn Linear Regression and Random Forest) and Technical Analysis (pandas/numpy) run **in-process directly within the Python Flask backend** on the server. They do NOT require an expensive separate microservice server. The AI Chatbot connects via secure HTTPS requests to Google Gemini or OpenAI when API keys are configured, and includes a deterministic offline financial reasoning engine that executes directly in Python.

---

## 2. Directory Hierarchy in VS Code

```text
STOCKSENSE_AI/
│
├── frontend/                               # User Interface (HTML, CSS, JavaScript)
│   ├── templates/                          # Jinja2 HTML views rendered by Flask
│   │   ├── base.html                       # Master layout (navbar, footer, chatbot drawer)
│   │   ├── login.html                      # User & Admin Login modal/tabs
│   │   ├── register.html                   # Account registration
│   │   ├── dashboard.html                  # Market summary, top gainers, losers
│   │   ├── stock_analysis.html             # Stock charts, technicals, ML, AI recommendation, buy modal
│   │   ├── markets.html                    # Indian market indices and sector overview
│   │   ├── watchlist.html                  # User favorited stocks
│   │   ├── portfolio.html                  # Virtual holdings, cash balance, transactions, sell modal
│   │   ├── profile.html                    # User account settings
│   │   ├── admin.html                      # Protected Admin Portal (user & wallet management)
│   │   └── 403.html                        # RBAC Access Forbidden page
│   │
│   └── static/                             # Static web assets served to browsers
│       ├── css/
│       │   ├── style.css                   # Global styles, variables, dark theme
│       │   ├── components.css              # Cards, buttons, tables, badges, modals
│       │   └── chatbot.css                 # AI Chatbot sliding drawer & chat bubbles
│       └── js/
│           ├── api.js                      # Centralized API fetch client with error handling
│           ├── auth.js                     # Authentication state, login, and registration logic
│           ├── dashboard.js                # Market indices and dashboard data fetching
│           ├── stock_analysis.js           # Chart.js charts, indicator toggles, ML triggers, buy action
│           ├── portfolio.js                # Portfolio stats, holdings table, sell action, transaction log
│           ├── watchlist.js                # Watchlist additions and price updates
│           ├── chatbot.js                  # Chat messages, quick suggestions, markdown rendering
│           └── profile.js                  # Profile management and wallet refresh
│
├── backend/                                # Application Backend Logic
│   └── app/
│       ├── __init__.py                     # Flask application factory (create_app)
│       ├── config.py                       # Configuration classes (Dev, Prod, Test)
│       ├── extensions.py                   # SQLAlchemy and CORS extension singletons
│       │
│       ├── models/                         # Database ORM Schemas (SQLAlchemy)
│       │   ├── user.py                     # User table, roles (user/admin), password hashing
│       │   ├── wallet.py                   # Virtual cash wallet for paper trading
│       │   ├── portfolio.py                # Holding (active stocks) and Transaction (history)
│       │   ├── stock.py                    # StockMetadata cache and RecentView
│       │   ├── watchlist.py                # User watchlist associations
│       │   └── audit.py                    # AdminAuditLog for virtual cash adjustments
│       │
│       ├── routes/                         # REST API & Page View Blueprints
│       │   ├── auth_routes.py              # /api/auth (register, login, logout, me)
│       │   ├── stock_routes.py             # /api/stocks (search, quote, history, technicals, predict)
│       │   ├── ml_routes.py                # /api/ml/predict (ML predictions and model metrics)
│       │   ├── recommendation_routes.py    # /api/recommendation (BUY/HOLD/SELL signals)
│       │   ├── chatbot_routes.py           # /api/chat (ask, history, suggestions)
│       │   ├── portfolio_routes.py         # /api/portfolio (buy, sell, summary, transactions)
│       │   ├── admin_routes.py             # /admin & /api/admin (users, wallet adjust, audit)
│       │   ├── watchlist_routes.py         # /api/watchlist (CRUD operations)
│       │   ├── user_routes.py              # /api/user (profile and wallet info)
│       │   └── view_routes.py              # HTML page rendering routes
│       │
│       ├── services/                       # Core Business Logic & Algorithms
│       │   ├── stock_service.py            # Market data retrieval (Upstox + yfinance fallback)
│       │   ├── upstox_service.py           # Upstox Developer API v2 integration
│       │   ├── instrument_mapping_service.py # NSE symbols to official ISIN & metadata
│       │   ├── technical_analysis_service.py # RSI, MACD, SMA 20, SMA 50, EMA, Bollinger Bands
│       │   ├── ml_service.py               # Linear Regression & Random Forest price forecasting
│       │   ├── recommendation_service.py   # Multi-factor decision scoring algorithm
│       │   ├── chatbot_service.py          # Grounded AI Chatbot engine (Gemini/OpenAI/Offline)
│       │   ├── paper_trading_service.py    # Virtual BUY/SELL execution and P/L calculation
│       │   ├── wallet_service.py           # Virtual cash balance management
│       │   ├── watchlist_service.py        # Watchlist persistence logic
│       │   └── auth_service.py             # Password hashing and token generation
│       │
│       └── utils/                          # Helpers and Security
│           ├── decorators.py               # @admin_required, @login_required, @token_required
│           ├── validators.py               # Input validation for email, username, password
│           └── helpers.py                  # Standardized JSON response formatters
│
├── tests/                                  # Automated Test Suite (105+ unit & integration tests)
│   ├── test_role_auth.py                   # RBAC User vs. Admin security tests
│   ├── test_paper_trading_buy.py           # Virtual Buy execution & cash validation
│   ├── test_paper_trading_sell.py          # Virtual Sell execution & P/L tests
│   ├── test_admin_dashboard.py             # Admin wallet modifications & audit tests
│   ├── test_ml_service.py                  # ML training, forecasting, and metric tests
│   ├── test_recommendation_service.py      # Recommendation score & decision logic tests
│   └── test_chatbot_service.py             # Chatbot grounding and response tests
│
├── docs/                                   # Documentation & Viva Guides
│   ├── PROJECT_STRUCTURE.md                # System architecture and data flow (this file)
│   └── CODE_LOCATION_GUIDE.md              # Software Engineering demo guide & viva cheat sheet
│
├── stocksense.db                           # Local SQLite Database (User accounts, holdings, cash)
├── init_db.py                              # Database initialization & NSE stock seeding script
├── create_admin.py                         # Admin account creation / promotion CLI tool
├── run.py                                  # Main application server startup entry point
├── requirements.txt                        # Python dependencies
├── README.md                               # Project overview and quick start guide
├── .env                                    # Local configuration & environment variables
└── .gitignore                              # Git exclusion rules
```

---

## 3. Detailed Layer-by-Layer Walkthrough

### Layer 1: Frontend (User Interface)
* **Technologies:** HTML5, Jinja2 template inheritance, Vanilla CSS, Vanilla JavaScript, Chart.js.
* **Responsibilities:**
  * Renders clean, modern dark-themed web pages without bulky UI frameworks.
  * Captures user interactions (symbol search, timeframe selection, buy/sell amounts, chat queries).
  * Calls backend REST API endpoints using asynchronous `fetch()` in `frontend/static/js/api.js`.
  * Dynamically updates Chart.js candlestick charts, line charts, indicator panels, and tables.

### Layer 2: Flask Backend (Routing & Authorization)
* **Technologies:** Python 3.10+, Flask, Werkzeug, PyJWT.
* **Responsibilities:**
  * Entry script `run.py` launches the WSGI application created by `backend/app/__init__.py:create_app()`.
  * Delegates requests across 10 modular blueprints (`backend/app/routes/`).
  * Enforces Role-Based Access Control (RBAC) via `@admin_required` and `@token_required` decorators in `backend/app/utils/decorators.py`.
  * Validates request payloads and returns standardized JSON responses `{ status: "success", data: ... }` via `helpers.py`.

### Layer 3: Business Logic & Quantitative Engines
* **Technologies:** Scikit-learn, Pandas, NumPy, Google Generative AI, OpenAI.
* **Responsibilities:**
  * **Technical Analysis (`technical_analysis_service.py`):** Calculates 14-period RSI, MACD (12, 26, 9), SMA 20, and SMA 50.
  * **Machine Learning (`ml_service.py`):** Prepares chronological lag features, trains Linear Regression and Random Forest models, forecasts future closing prices, and computes MSE, RMSE, MAE, and $R^2$ scores.
  * **AI Recommendation Engine (`recommendation_service.py`):** Weighs technical indicators (55%) and ML forecasts (35%) into a score between -100 and +100 to produce an actionable BUY, HOLD, or SELL rating with human-readable rationale.
  * **AI Chatbot (`chatbot_service.py`):** Ingests live stock data, indicators, ML forecasts, and company information into the LLM context prompt to generate accurate, hallucination-free answers.
  * **Paper Trading (`paper_trading_service.py`):** Validates virtual cash availability against real-time market prices, records holdings with weighted average costs, and computes realized profit/loss.

### Layer 4: Persistence & External Integration
* **Technologies:** SQLAlchemy ORM, SQLite (`stocksense.db`), Upstox API v2, yfinance.
* **Responsibilities:**
  * SQLAlchemy ORM connects the backend to `stocksense.db` (or MySQL if configured).
  * Manages relational integrity across `User`, `Wallet`, `Holding`, `Transaction`, and `AdminAuditLog`.
  * Fetches authoritative market data from the Upstox Developer API with an automatic `yfinance` fallback.

---

## 4. Key End-to-End Scenarios

### Scenario A: Analyzing an Indian Stock (e.g., RELIANCE)
1. User enters `RELIANCE` in the search bar on `stock_analysis.html`.
2. Frontend calls `/api/stocks/RELIANCE` to fetch current quote and company metadata.
3. Frontend requests `/api/stocks/RELIANCE/history?range=1y` for historical daily candles.
4. Frontend requests `/api/stocks/RELIANCE/technicals` to calculate RSI, MACD, and Moving Averages.
5. Frontend requests `/api/stocks/RELIANCE/predict` to train ML models and predict upcoming prices.
6. Frontend requests `/api/recommendation/RELIANCE` for the multi-indicator BUY / HOLD / SELL decision.
7. `stock_analysis.js` paints the candlestick chart, overlays SMA 20 / SMA 50, renders RSI / MACD sub-charts, displays ML predictions, and highlights the AI recommendation badge.

### Scenario B: Executing a Simulated Paper Trade BUY Order
1. User clicks "Buy Shares" on `stock_analysis.html` and inputs quantity (e.g., 5 shares).
2. Frontend sends `POST /api/portfolio/buy` with `{ symbol: "RELIANCE", quantity: 5 }` and user authentication.
3. Backend fetches the authoritative live market price of RELIANCE (e.g., ₹2,950.00).
4. `PaperTradingService` calculates total cost = 5 × ₹2,950.00 = ₹14,750.00.
5. Service checks the user's `Wallet.virtual_cash`. If balance < ₹14,750, it returns a 400 error.
6. If balance is sufficient, the backend deducts ₹14,750 from `Wallet`, creates or updates the `Holding` with the weighted average buy price, and records an entry in `Transaction`.
7. Backend returns the updated cash balance and holding details to the frontend.

### Scenario C: Role-Based Access Control (RBAC) Enforcement
1. A standard registered user attempts to navigate to `http://127.0.0.1:5000/admin`.
2. The route in `backend/app/routes/admin_routes.py` has the `@admin_required` decorator.
3. `@admin_required` reads the user's record from `User` model and inspects the `role` column.
4. If `role != 'admin'`, access is immediately blocked and Flask renders `403.html` (or returns `{ status: "error", code: 403 }`).
5. Only users created or promoted via `create_admin.py` with `role == 'admin'` are allowed into the Admin Portal.
