# StockSense AI — Functional Testing Documentation (Selenium & Pytest)

## 1. Overview & Objective
This document outlines the **Automated Functional Testing** implementation for **StockSense AI**, an Indian stock analysis and paper-trading platform. 

The primary objective of this test suite is to verify the correctness of the **Authentication Subsystem**, **Session Management**, and **Role-Based Access Control (RBAC)** across standard users and administrators. The tests are executed directly against the browser interface using **Selenium WebDriver** and **pytest**.

---

## 2. Technology Stack & Prerequisites

| Component | Technology / Specification | Purpose |
| :--- | :--- | :--- |
| **Test Runner** | `pytest (>=8.0.0)` | Test execution, reporting, and fixtures |
| **Browser Automation** | `selenium (>=4.20.0)` | Direct browser interaction via W3C WebDriver |
| **Target Browser** | Google Chrome (Headless mode) / Microsoft Edge fallback | Automated browser rendering |
| **Application Backend** | Python 3.10 Flask 3.0.3 | Web server and API endpoints |
| **Database** | SQLite (`stocksense.db`) | Read-only verification (No data mutation) |

---

## 3. Security, Test Isolation & Data Safety

To adhere to rigorous software engineering and financial platform standards:
1. **Zero Secret Exposure**: Passwords and secrets are never hardcoded in test scripts. Test credentials are read from dedicated environment variables (`TEST_USER_USERNAME`, `TEST_USER_PASSWORD`, `TEST_ADMIN_USERNAME`, `TEST_ADMIN_PASSWORD`).
2. **Database Integrity**: The functional test cases are strictly read-only authentication and authorization checks. They do not reset, alter, or insert dummy trading transactions, virtual cash, or user records into `stocksense.db`.
3. **Session & Process Isolation**:
   - Each test method runs in a dedicated browser session initialized with a clean cookie jar and storage sandbox (`driver` fixture with function scope).
   - If an existing application server is running on `http://127.0.0.1:5000`, the suite connects to it. If not, the test runner automatically spins up an isolated background Flask test instance on port `5001`.

---

## 4. Verified HTML Elements & Route Selectors

Tests interact with actual project routes and verified DOM elements:

| Route / View | DOM Element / Selector | Function |
| :--- | :--- | :--- |
| `/login` | `#login-form` | Main authentication form container |
| `/login` | `#identifier` | Username or email input field (`required`, `type="text"`) |
| `/login` | `#password` | Password input field (`required`, `type="password"`) |
| `/login` | `#login-submit-btn` | Submit action button (`"Sign In as User"` / `"Sign In as Admin"`) |
| `/login` | `#tab-user-role` | Role switch button for standard user |
| `/login` | `#tab-admin-role` | Role switch button for system administrator |
| `/login` | `#auth-error-alert` | Bootstrap alert container for authentication errors |
| `/dashboard` | `title` / `#market-indices-grid` | Authenticated standard user landing dashboard |
| `/admin` | `title` / `.admin-navbar` | Protected administrative surveillance portal |
| `/admin` (non-admin) | `title` / `.badge` / `403.html` | HTTP 403 Forbidden template with RBAC explanation |

---

## 5. Detailed Test Cases & Execution Results

### Summary of Test Run
- **Test File**: `tests/test_authentication.py`
- **Execution Date**: 16 October 2026
- **Test Results**: **6 Passed, 0 Failed, 0 Skipped (100% Pass Rate)**
- **Total Execution Time**: **51.25 seconds**

```
tests/test_authentication.py::test_1_login_page_loads PASSED             [ 16%]
tests/test_authentication.py::test_2_valid_user_login PASSED             [ 33%]
tests/test_authentication.py::test_3_invalid_password_rejected PASSED    [ 50%]
tests/test_authentication.py::test_4_empty_login_fields_validation PASSED [ 66%]
tests/test_authentication.py::test_5_user_access_to_admin_page_denied PASSED [ 83%]
tests/test_authentication.py::test_6_admin_login_and_portal_access PASSED [100%]

============================= 6 passed in 51.25s ==============================
```

---

### Test Case Breakdown

#### TEST 1: Login Page Verification
- **Test Function**: `test_1_login_page_loads`
- **Objective**: Verify that the login view renders correctly with required form controls.
- **Preconditions**: Application server running.
- **Steps**:
  1. Navigate to `/login`.
  2. Verify browser title contains `"Login - StockSense AI"`.
  3. Verify visibility of `#login-form`, `#identifier`, `#password`, and `#login-submit-btn`.
  4. Verify that `#tab-user-role` and `#tab-admin-role` exist.
- **Expected Result**: Page loads with status 200; all inputs and buttons are visible and active.
- **Actual Result**: **PASSED** (Form loaded, inputs visible with correct HTML attributes).

#### TEST 2: Valid User Authentication
- **Test Function**: `test_2_valid_user_login`
- **Objective**: Verify that a registered standard user can authenticate and reach the user dashboard.
- **Preconditions**: Test user exists in database (`demo_user`).
- **Steps**:
  1. Open `/login`.
  2. Enter valid test username (`demo_user`) and password (`password123`).
  3. Click `#login-submit-btn`.
  4. Wait explicitly for URL redirection.
- **Expected Result**: User authenticated via JWT and Flask session; browser redirects to `/dashboard`.
- **Actual Result**: **PASSED** (Browser navigated to `/dashboard`, page title confirmed `"Dashboard - StockSense AI"`).

#### TEST 3: Invalid Password Rejection
- **Test Function**: `test_3_invalid_password_rejected`
- **Objective**: Verify authentication failure and user notification when an invalid password is entered.
- **Preconditions**: Test user exists in database.
- **Steps**:
  1. Open `/login`.
  2. Enter valid username (`demo_user`) and invalid password (`WrongInvalidPassword!2026`).
  3. Click `#login-submit-btn`.
  4. Wait for `#auth-error-alert` to display.
- **Expected Result**: Authentication rejected with HTTP 401; `#auth-error-alert` is displayed with error message; browser remains on `/login`.
- **Actual Result**: **PASSED** (Error banner displayed: *"Invalid credentials. Please verify your username and password."* User remained on `/login`).

#### TEST 4: Empty Login Fields Validation
- **Test Function**: `test_4_empty_login_fields_validation`
- **Objective**: Verify that submitting empty credentials triggers client-side required-field constraints.
- **Preconditions**: Open `/login`.
- **Steps**:
  1. Clear identifier and password inputs.
  2. Verify HTML5 validity check on `#identifier`.
  3. Attempt form submission.
- **Expected Result**: Browser HTML5 validation prevents submission (`checkValidity() == False`); page does not navigate away.
- **Actual Result**: **PASSED** (Constraint validation triggered; browser remained on `/login`).

#### TEST 5: Role-Based Access Control (RBAC) — User Denied from Admin Page
- **Test Function**: `test_5_user_access_to_admin_page_denied`
- **Objective**: Verify that an authenticated standard user cannot access the protected `/admin` route.
- **Preconditions**: Standard user (`demo_user`) authenticated.
- **Steps**:
  1. Log in as standard user.
  2. Directly navigate to `/admin`.
  3. Observe response and rendered template.
- **Expected Result**: The backend `@admin_required` decorator validates user role (`user != admin`), returning HTTP 403 and rendering the `403.html` template.
- **Actual Result**: **PASSED** (Page rendered `403.html` with title `"403 - Access Forbidden | StockSense AI"` and heading *"Administrator Access Required"*).

#### TEST 6: Administrator Login & Portal Access
- **Test Function**: `test_6_admin_login_and_portal_access`
- **Objective**: Verify that an authorized administrator can log in via the Admin Login tab and reach the Admin Portal.
- **Preconditions**: Admin user (`admin`) exists in database.
- **Steps**:
  1. Open `/login`.
  2. Click `#tab-admin-role` to switch role context.
  3. Enter admin credentials.
  4. Click `#login-submit-btn`.
  5. Wait for URL transition.
- **Expected Result**: Admin authenticated; redirected to `/admin`; Admin Portal rendered with administrative controls.
- **Actual Result**: **PASSED** (Redirected to `/admin`; page title confirmed `"Admin Portal - StockSense AI"`).

---

## 6. How to Run the Tests Locally

### Step 1: Open Terminal in Project Directory
```powershell
cd c:\Users\ramir\OneDrive\Documents\STOCKSENSE_AI
```

### Step 2: (Optional) Set Custom Test Credentials
```powershell
$env:TEST_USER_USERNAME = "demo_user"
$env:TEST_USER_PASSWORD = "password123"
$env:TEST_ADMIN_USERNAME = "admin"
$env:TEST_ADMIN_PASSWORD = "AdminPassword123!"
```

### Step 3: Run Selenium Tests via Pytest
```powershell
python -m pytest tests/test_authentication.py -v
```

### Step 4: Run with Browser Visible (Non-Headless Demo Mode)
To show the browser window to faculty/examiners during a project demo:
```powershell
$env:HEADLESS = "false"
python -m pytest tests/test_authentication.py -v
```

---

## 7. College Faculty Demonstration Guide

When presenting this functional testing work to your faculty or external examiner:

1. **Explain the Two User Personas**:
   - Persona A: Standard Retail Trader (`role='user'`), access to market charts, AI chatbot, and paper-trading portfolio.
   - Persona B: Compliance Administrator (`role='admin'`), access to user directories, audit logs, and platform surveillance.
2. **Highlight RBAC Security**:
   - Point to **TEST 5**: Show that directly typing `/admin` in the browser while logged in as a normal user triggers HTTP 403 Forbidden rather than exposing sensitive administration screens.
3. **Show Test Isolation**:
   - Explain that each test opens a clean browser instance (`driver` fixture), ensuring that cookies from the admin session do not leak into the user session.
4. **Execution Proof**:
   - Show the terminal output showing `6 passed in 51.25s`.
