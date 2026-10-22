# StockSense AI — Code Location & Software Engineering Demo Guide

This guide is designed for your **Software Engineering Project Demo / Viva**. When your professor ("Mam") asks to see any feature, concept, algorithm, or file, use this document to open the exact file and navigate directly to the key function.

---

## 1. Quick Master Reference Table

| What Mam Asks | Folder / File to Open in VS Code | Key Class / Function | What It Does |
| :--- | :--- | :--- | :--- |
| **Frontend Templates** | `frontend/templates/` | `base.html`, `stock_analysis.html` | All Jinja2 HTML views rendered to the user |
| **CSS Styling** | `frontend/static/css/` | `style.css`, `components.css`, `chatbot.css` | UI visual design, dark theme, and component styling |
| **JavaScript Code** | `frontend/static/js/` | `stock_analysis.js`, `portfolio.js`, `api.js` | Interactive frontend logic, charts, and API calls |
| **Backend Entry Point** | `run.py` & `backend/app/__init__.py` | `create_app()` | Initializes Flask, extensions, blueprints, and starts server |
| **Login / Register** | `backend/app/routes/auth_routes.py` & `backend/app/services/auth_service.py` | `AuthService.register_user()`, `login_user()` | Authenticates users, validates passwords, issues JWT/sessions |
| **RBAC Security** | `backend/app/utils/decorators.py` | `@admin_required`, `@token_required` | Restricts User vs. Admin routes (returns 403 Forbidden) |
| **Database Models** | `backend/app/models/` | `User`, `Holding`, `Transaction`, `Wallet` | SQLAlchemy ORM definitions for tables and relations |
| **Database & Seeding** | `stocksense.db` & `init_db.py` | `init_database()` | Stores application data; seeds Indian stocks and demo user |
| **Stock Market API** | `backend/app/services/stock_service.py` & `upstox_service.py` | `StockService.get_stock_quote()`, `get_stock_history()` | Fetches live and historical NSE market data via Upstox / yfinance |
| **Technical Analysis** | `backend/app/services/technical_analysis_service.py` | `TechnicalAnalysisService.calculate_indicators()` | Calculates RSI 14, MACD (12, 26, 9), SMA 20, SMA 50, EMA 20 |
| **ML Algorithms** | `backend/app/services/ml_service.py` | `MLService.train_models()`, `predict()` | Scikit-learn Linear Regression and Random Forest Regressor |
| **ML Evaluation Metrics**| `backend/app/services/ml_service.py` | `mean_squared_error()`, `r2_score()` | Calculates MSE, RMSE, MAE, and R² accuracy metrics |
| **AI Recommendation** | `backend/app/services/recommendation_service.py` | `RecommendationService.generate_recommendation()` | Generates BUY / HOLD / SELL signals with multi-indicator score |
| **AI Chatbot** | `backend/app/services/chatbot_service.py` & `backend/app/routes/chatbot_routes.py` | `ChatbotService.ask()` | Grounded Indian stock AI assistant with LLM and offline engines |
| **Paper Trading** | `backend/app/services/paper_trading_service.py` & `backend/app/routes/portfolio_routes.py` | `PaperTradingService.buy_stock()`, `sell_stock()` | Executes virtual stock purchases and sales with wallet validation |
| **Portfolio & Holdings** | `backend/app/services/paper_trading_service.py` & `wallet_service.py` | `PaperTradingService.get_portfolio_summary()` | Calculates invested capital, current market value, and unrealized P/L |
| **Transaction History** | `backend/app/services/paper_trading_service.py` | `PaperTradingService.get_user_transactions()` | Records and retrieves buy/sell execution history and realized P/L |
| **Admin Dashboard** | `backend/app/routes/admin_routes.py` & `frontend/templates/admin.html` | `admin_add_virtual_money()`, `get_all_users()` | Admin operations, user directory, and virtual cash management |
| **App Configuration** | `backend/app/config.py` & `.env` | `Config`, `DevelopmentConfig` | Loads environment variables, DB URI, API keys, and timeouts |
| **Dependencies** | `requirements.txt` | N/A | Lists required Python packages and versions |

---

## 2. Detailed Breakdown of Every Key File

### 1. Backend Entry Point: `run.py`
* **Purpose:** Acts as the executable Python entry script that boots the local development server.
* **Main Function / Code to Look For:** `app = create_app(...)` and `app.run(host=host, port=port, debug=debug)`.
* **How It Connects:** Imports the `create_app` factory from `backend/app/__init__.py` and runs the WSGI server on port 5000.

### 2. Application Factory: `backend/app/__init__.py`
* **Purpose:** Configures Flask, initializes extensions (SQLAlchemy, CORS), registers all 10 Blueprints, and verifies DB schemas.
* **Main Function / Code to Look For:** `create_app(config_name)`.
* **How It Connects:** Acts as the central hub connecting config (`config.py`), database (`extensions.py`), route blueprints (`backend/app/routes/`), and frontend templates/static files.

### 3. Application Configuration: `backend/app/config.py`
* **Purpose:** Manages application settings, database connection strings, JWT expiry, and external API configurations across development, testing, and production environments.
* **Main Class / Function to Look For:** `Config` class and `Config.get_database_uri()`.
* **How It Connects:** Supplies configuration parameters to `create_app()` and determines whether to connect to SQLite (`stocksense.db`) or MySQL.

### 4. Authentication Service: `backend/app/services/auth_service.py`
* **Purpose:** Handles user account registration, login verification, password hashing, and authentication token issuance.
* **Main Class / Function to Look For:** `AuthService.register_user()` and `AuthService.login_user()`.
* **How It Connects:** Called by `backend/app/routes/auth_routes.py` and interacts directly with the `User` model in `backend/app/models/user.py`.

### 5. Role-Based Access Control (RBAC): `backend/app/utils/decorators.py`
* **Purpose:** Enforces endpoint authorization using custom Python function decorators that check user roles before allowing access.
* **Main Decorators to Look For:** `@login_required`, `@token_required`, and `@admin_required`.
* **How It Connects:** Applied on routes in `backend/app/routes/admin_routes.py` and `portfolio_routes.py` to block unauthorized users with an HTTP 403 Forbidden status code.

### 6. Database Models: `backend/app/models/`
* **Purpose:** Defines the relational database tables, columns, foreign keys, and relationships via SQLAlchemy ORM.
* **Key Files & Classes:**
  * `backend/app/models/user.py`: `User` model storing credentials, role (`user` vs `admin`), and relationships to wallet and watchlist.
  * `backend/app/models/wallet.py`: `Wallet` model storing each user's isolated virtual cash balance.
  * `backend/app/models/portfolio.py`: `Holding` (active stock inventory with average price) and `Transaction` (log of BUY/SELL orders and realized P/L).
  * `backend/app/models/stock.py`: `StockMetadata` (cached Indian stock symbols and sectors) and `RecentView`.
  * `backend/app/models/audit.py`: `AdminAuditLog` (tracks administrative wallet modifications and grants).
* **How It Connects:** Used across all services to perform database operations without raw SQL queries.

### 7. Database Initialization & Seeding: `init_db.py`
* **Purpose:** Creates SQLite tables if missing, adds required schema columns, and seeds 50+ top NSE stocks along with a starter demo user.
* **Main Function to Look For:** `init_database()`.
* **How It Connects:** Uses `create_app()` context to initialize the database file `stocksense.db` before the first run.

### 8. Admin Account Provisioning CLI: `create_admin.py`
* **Purpose:** Allows administrators to securely create or promote an admin account via command line.
* **Main Function to Look For:** `create_or_promote_admin(username, email, password)`.
* **How It Connects:** Updates the `role` column in the `User` model to `'admin'`.

### 9. Stock Market Data Service: `backend/app/services/stock_service.py`
* **Purpose:** Fetches real-time stock quotes, company profiles, top market gainers/losers, and historical candlestick data.
* **Main Class / Function to Look For:** `StockService.get_stock_quote()` and `StockService.get_stock_history()`.
* **How It Connects:** Uses Upstox API (`upstox_service.py`) for live quotes with an automatic fallback to `yfinance` (.NS Indian tickers). Supplies data to technical analysis, ML, and frontend routes.

### 10. Technical Analysis Engine: `backend/app/services/technical_analysis_service.py`
* **Purpose:** Computes mathematical quantitative trading indicators using `pandas` and `numpy` from historical closing prices.
* **Main Class / Function to Look For:** `TechnicalAnalysisService.calculate_indicators()`.
* **Key Math Formulas Inside:**
  * **RSI (14):** Relative Strength Index using 14-period average gains vs. average losses.
  * **MACD:** Fast 12 EMA minus Slow 26 EMA; 9 EMA Signal line; Histogram difference.
  * **Moving Averages:** 20-day Simple Moving Average (SMA 20) and 50-day Simple Moving Average (SMA 50).
  * **Bollinger Bands:** 20 SMA ± 2 standard deviations.
* **How It Connects:** Feeds indicator values directly into `recommendation_service.py`, `chatbot_service.py`, and the interactive charts in `stock_analysis.html`.

### 11. Machine Learning Prediction Engine: `backend/app/services/ml_service.py`
* **Purpose:** Trains regression models on historical time-series data to forecast future stock prices for 7 to 30 days.
* **Main Class / Function to Look For:** `MLService.prepare_features()`, `MLService.train_models()`, and `MLService.predict()`.
* **Algorithms Implemented:** Scikit-learn `LinearRegression` (trend baseline) and `RandomForestRegressor` (non-linear ensemble).
* **Metrics Computed:** Mean Squared Error (MSE), Root Mean Squared Error (RMSE), Mean Absolute Error (MAE), and R-squared ($R^2$) score.
* **How It Connects:** Called by `backend/app/routes/ml_routes.py` and factored into the AI recommendation score.

### 12. AI Recommendation Decision Engine: `backend/app/services/recommendation_service.py`
* **Purpose:** Combines technical indicators and ML forecasts into an explainable multi-indicator scoring algorithm that generates BUY, HOLD, or SELL signals.
* **Main Class / Function to Look For:** `RecommendationService.generate_recommendation()`.
* **How It Works:** Weights RSI (20%), MACD (20%), MA20/MA50 trend alignment (25%), and ML forecast (35%) into a score between -100 and +100 with clear natural-language rationale.
* **How It Connects:** Displayed on `stock_analysis.html` and queried by the AI Chatbot.

### 13. AI Stock Chatbot Service: `backend/app/services/chatbot_service.py`
* **Purpose:** Answers user questions about the selected stock with zero hallucination by injecting real-time live price, RSI, MACD, MA, ML prediction, and recommendation data.
* **Main Class / Function to Look For:** `ChatbotService.ask()`.
* **How It Works:** Supports Google Gemini API (`gemini-1.5-flash`) or OpenAI (`gpt-4o-mini`) via environment variables, with a deterministic quantitative financial reasoning engine that functions offline.
* **How It Connects:** Exposed via `backend/app/routes/chatbot_routes.py` and rendered by `frontend/static/js/chatbot.js`.

### 14. Paper Trading Engine: `backend/app/services/paper_trading_service.py`
* **Purpose:** Executes simulated buying and selling of Indian stocks with live market prices, validating virtual cash balances and computing realized profit/loss.
* **Main Class / Function to Look For:** `PaperTradingService.buy_stock()` and `PaperTradingService.sell_stock()`.
* **How It Connects:** Deducts/credits money from `Wallet`, records new `Holding` entries or updates weighted average cost, records `Transaction` entries, and powers `portfolio.html`.

### 15. Portfolio Analytics & Wallet Service: `backend/app/services/wallet_service.py`
* **Purpose:** Manages user virtual cash balances, creates starting ₹10,000 balances for new users, and provides administrative balance adjustments.
* **Main Class / Function to Look For:** `WalletService.get_or_create_wallet()` and `WalletService.admin_modify_balance()`.
* **How It Connects:** Coordinates with `PaperTradingService` and `AdminAuditLog`.

### 16. Admin Routes & Management: `backend/app/routes/admin_routes.py`
* **Purpose:** Provides administrative REST API endpoints for user inspection, system-wide transaction activity streams, virtual cash adjustments, and audit log inspection.
* **Main Functions to Look For:** `get_all_users()`, `get_user_details()`, and `admin_add_virtual_money()`.
* **How It Connects:** Feeds data into `frontend/templates/admin.html` and records actions in `AdminAuditLog`.

### 17. Frontend Stock Analysis Dashboard: `frontend/templates/stock_analysis.html` & `frontend/static/js/stock_analysis.js`
* **Purpose:** Main trading and analysis workstation displaying interactive Chart.js price charts, technical indicator toggles (RSI, MACD, MA), ML price forecast curves, AI recommendation cards, and the paper trading order execution modal.
* **How It Connects:** Calls `/api/stocks/<symbol>`, `/api/stocks/<symbol>/history`, `/api/stocks/<symbol>/technicals`, `/api/stocks/<symbol>/predict`, `/api/recommendation/<symbol>`, and `/api/portfolio/buy`.

### 18. Frontend Portfolio & Orders: `frontend/templates/portfolio.html` & `frontend/static/js/portfolio.js`
* **Purpose:** Shows user's virtual net worth, available cash, total invested, current market valuation, overall profit/loss %, holdings table with active "Sell" buttons, and full transaction history.
* **How It Connects:** Calls `/api/portfolio/summary` and `/api/portfolio/sell`.

---

## 3. "If Mam Asks..." Quick Viva Cheat Sheet

### Q1: "Show me your Frontend and UI Design"
1. **Open:** `frontend/templates/stock_analysis.html` and `frontend/static/css/style.css`.
2. **What to Say:** "Mam, our frontend uses HTML5 templates powered by Jinja2, styled with custom Vanilla CSS for a responsive modern dark theme. We use Chart.js in `stock_analysis.js` to render interactive candlestick and indicator charts."

### Q2: "Where does your backend start and how is it structured?"
1. **Open:** `run.py` and `backend/app/__init__.py`.
2. **Point to:** Lines 6-56 in `backend/app/__init__.py` (`create_app()`).
3. **What to Say:** "Mam, `run.py` is the execution entry point. It calls `create_app()` inside `backend/app/__init__.py`, which uses Flask's Application Factory pattern. Here we initialize SQLAlchemy, setup CORS, and register 10 modular blueprints for authentication, stocks, ML, recommendations, chatbot, portfolio, and admin."

### Q3: "Where is user login, password hashing, and authentication?"
1. **Open:** `backend/app/services/auth_service.py`.
2. **Point to:** `AuthService.register_user()` (hashes password using `generate_password_hash`) and `AuthService.login_user()` (`check_password_hash`).
3. **What to Say:** "Mam, user passwords are encrypted using secure cryptographic hashing before saving to the database. We support both JWT bearer tokens and Flask sessions for state management."

### Q4: "Show me your Role-Based Access Control (RBAC) security"
1. **Open:** `backend/app/utils/decorators.py` and `backend/app/routes/admin_routes.py`.
2. **Point to:** The `@admin_required` decorator in `decorators.py` and its application on `/admin` and `/api/admin/*` routes in `admin_routes.py`.
3. **What to Say:** "Mam, we implemented RBAC using Python decorators. `@admin_required` inspects the authenticated user's `role` column in the database. If a standard user attempts to access administrative endpoints or pages, the decorator immediately rejects the request with an HTTP 403 Forbidden."

### Q5: "Where are the database tables defined?"
1. **Open:** `backend/app/models/user.py`, `backend/app/models/portfolio.py`, and `backend/app/models/wallet.py`.
2. **Point to:** `class User(db.Model)`, `class Holding(db.Model)`, `class Transaction(db.Model)`, and `class Wallet(db.Model)`.
3. **What to Say:** "Mam, we use SQLAlchemy ORM models. Each user has an isolated virtual `Wallet`, multiple `Holding` records representing current stock inventory, and a permanent `Transaction` log tracking every simulated buy and sell order."

### Q6: "Where does the stock market data come from?"
1. **Open:** `backend/app/services/stock_service.py` and `backend/app/services/upstox_service.py`.
2. **Point to:** `StockService.get_stock_quote()` and `StockService.get_stock_history()`.
3. **What to Say:** "Mam, our market service connects to the official Upstox Developer API v2 for real-time market quotes and historical data. We also have an automatic fallback to `yfinance` with Indian NSE symbols (`.NS`), ensuring continuous availability during market closures."

### Q7: "Show me the technical analysis code for RSI, MACD, and Moving Averages"
1. **Open:** `backend/app/services/technical_analysis_service.py`.
2. **Point to:**
   * Line 55: `df['SMA_20'] = closes.rolling(window=20).mean()`
   * Line 56: `df['SMA_50'] = closes.rolling(window=50).mean()`
   * Line 61-68: 14-period RSI formula: $Gain / Loss \rightarrow 100 - (100 / (1 + RS))$
   * Line 71-77: MACD formula: 12-day EMA minus 26-day EMA, and 9-day Signal line.
3. **What to Say:** "Mam, we calculate mathematical technical indicators from historical prices using `pandas` and `numpy`. We calculate 20-day and 50-day Simple Moving Averages, 14-day Relative Strength Index (RSI), and MACD with its Signal line and Histogram."

### Q8: "Where is your Machine Learning model implemented and how does it predict prices?"
1. **Open:** `backend/app/services/ml_service.py`.
2. **Point to:**
   * `prepare_features()`: Feature engineering (Open, High, Low, Close, Volume, Previous Close, MA20, MA50).
   * `train_models()`: Scikit-learn `LinearRegression()` and `RandomForestRegressor()`.
   * `predict()`: Time-series forecasting for upcoming sessions.
   * Model evaluation lines: `mean_squared_error(y_test, y_pred)` and `r2_score(y_test, y_pred)`.
3. **What to Say:** "Mam, our ML pipeline runs in `ml_service.py`. We take historical OHLCV data, compute moving average features, and train two models: Linear Regression for underlying trend direction, and Random Forest for non-linear patterns. We evaluate them using MSE, RMSE, MAE, and $R^2$ accuracy scores."

### Q9: "How does the AI Recommendation (BUY / HOLD / SELL) work?"
1. **Open:** `backend/app/services/recommendation_service.py`.
2. **Point to:** `generate_recommendation()` and scoring constants (RSI: 20 pts, MACD: 20 pts, Moving Averages: 25 pts, ML: 35 pts).
3. **What to Say:** "Mam, rather than relying on a single indicator, our system uses an explainable multi-factor decision engine. It evaluates RSI overbought/oversold levels, MACD crossovers, MA20/MA50 trend alignment, and ML predicted trajectory to produce a composite score from -100 to +100, which maps to BUY, HOLD, or SELL with full reasoning."

### Q10: "Show me the AI Chatbot code"
1. **Open:** `backend/app/services/chatbot_service.py` and `backend/app/routes/chatbot_routes.py`.
2. **Point to:** `ChatbotService.normalize_context()` and `ChatbotService.ask()`.
3. **What to Say:** "Mam, our chatbot is context-grounded. Before generating an answer, it gathers live market prices, technical indicators (RSI, MACD), ML predictions, and AI recommendations for the currently selected stock. This prevents hallucination. We connect to Google Gemini / OpenAI via API, and we also have a deterministic financial reasoning engine built-in."

### Q11: "How does Paper Trading work when a user Buys or Sells?"
1. **Open:** `backend/app/services/paper_trading_service.py`.
2. **Point to:**
   * `buy_stock()`: Checks virtual wallet balance, calculates `total_cost = live_price * qty`, deducts cash, and creates/updates the holding with a weighted average price.
   * `sell_stock()`: Checks quantity owned, calculates `sell_value = live_price * qty`, calculates `realized_pnl = (sell_price - avg_buy_price) * qty`, credits cash back to wallet, and records a transaction.
3. **What to Say:** "Mam, paper trading is completely validated on the backend. When a user buys, we fetch the live market price, ensure their virtual cash balance is sufficient, deduct funds, and update their portfolio holding. When selling, we calculate realized profit or loss and return funds to their virtual wallet."

### Q12: "Where is the Admin Portal and how do admins manage virtual cash?"
1. **Open:** `backend/app/routes/admin_routes.py` and `frontend/templates/admin.html`.
2. **Point to:** Line 238 in `admin_routes.py` (`admin_add_virtual_money`) and `AdminAuditLog`.
3. **What to Say:** "Mam, the Admin Portal allows administrators to inspect all registered users, monitor platform-wide paper trading trades in real-time, adjust user virtual cash balances, and view an immutable audit log of administrative actions."
