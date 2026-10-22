"""
StockSense AI - Selenium Functional Browser Automation Test Suite
==================================================================
Tests automated browser interactions for authentication, session management,
and Role-Based Access Control (RBAC) in StockSense AI.

Test Cases Implemented:
- TEST 1: Login page load, input fields, role selectors, and submit button presence.
- TEST 2: Valid user authentication with dedicated test user and dashboard redirection.
- TEST 3: Invalid password rejection, error alert display, and session protection.
- TEST 4: Empty login fields validation (HTML5 required constraint and JS validation).
- TEST 5: RBAC enforcement - standard user restricted from accessing /admin (403 Forbidden).
- TEST 6: Admin login with dedicated test administrator and Admin Portal access.

Execution:
    pytest tests/test_authentication.py -v
"""

import os
import sys
import time
import socket
import threading
import requests
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app import create_app

# ============================================================================
# Security & Test Credentials Configuration
# Reads from dedicated environment variables to avoid exposing credentials.
# Default demo accounts are pre-seeded in the database for demonstration.
# ============================================================================
TEST_USER_USERNAME = os.getenv("TEST_USER_USERNAME", "demo_user")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD", "password123")

TEST_ADMIN_USERNAME = os.getenv("TEST_ADMIN_USERNAME", "admin")
TEST_ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "AdminPassword123!")

DEFAULT_SERVER_PORT = int(os.getenv("TEST_SERVER_PORT", "5001"))
SERVER_HOST = os.getenv("TEST_SERVER_HOST", "127.0.0.1")
HEADLESS_MODE = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Checks if a local TCP port is already listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def wait_for_server(url: str, timeout: int = 15) -> bool:
    """Polls the HTTP server until it responds with a 200 OK status."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            res = requests.get(f"{url}/login", timeout=1)
            if res.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.3)
    return False


@pytest.fixture(scope="session")
def base_url():
    """
    Session fixture that ensures a running StockSense AI Flask server.
    If an instance is already running on port 5000, it binds to it.
    Otherwise, it starts a dedicated background test server on port 5001.
    """
    if is_port_in_use(5000, SERVER_HOST):
        url = f"http://{SERVER_HOST}:5000"
        if wait_for_server(url, timeout=3):
            yield url
            return

    # Start an isolated background Flask test instance on test port
    test_port = DEFAULT_SERVER_PORT
    app = create_app("development")
    
    server_thread = threading.Thread(
        target=app.run,
        kwargs={
            "host": SERVER_HOST,
            "port": test_port,
            "debug": False,
            "use_reloader": False,
        },
        daemon=True,
    )
    server_thread.start()

    url = f"http://{SERVER_HOST}:{test_port}"
    server_ready = wait_for_server(url, timeout=15)
    if not server_ready:
        pytest.fail(f"Could not connect to Flask application server at {url} within 15 seconds.")

    yield url


@pytest.fixture(scope="function")
def driver():
    """
    Function-scoped Selenium WebDriver fixture.
    Initializes a fresh, isolated browser instance per test to prevent
    cookie or session state contamination across tests.
    """
    driver_instance = None
    
    # 1. Attempt Chrome initialization
    try:
        chrome_opts = ChromeOptions()
        if HEADLESS_MODE:
            chrome_opts.add_argument("--headless=new")
        chrome_opts.add_argument("--disable-gpu")
        chrome_opts.add_argument("--no-sandbox")
        chrome_opts.add_argument("--disable-dev-shm-usage")
        chrome_opts.add_argument("--window-size=1280,800")
        chrome_opts.add_argument("--log-level=3")
        driver_instance = webdriver.Chrome(options=chrome_opts)
    except Exception as chrome_err:
        # 2. Fallback to Edge if Chrome is unavailable
        try:
            edge_opts = EdgeOptions()
            if HEADLESS_MODE:
                edge_opts.add_argument("--headless=new")
            edge_opts.add_argument("--disable-gpu")
            edge_opts.add_argument("--no-sandbox")
            edge_opts.add_argument("--window-size=1280,800")
            driver_instance = webdriver.Edge(options=edge_opts)
        except Exception as edge_err:
            pytest.fail(
                f"Failed to launch Chrome or Edge via Selenium:\n"
                f"Chrome error: {chrome_err}\n"
                f"Edge error: {edge_err}"
            )

    driver_instance.implicitly_wait(2)
    yield driver_instance
    try:
        driver_instance.quit()
    except Exception:
        pass


# ============================================================================
# Functional Browser Automation Test Cases
# ============================================================================

def test_1_login_page_loads(driver, base_url):
    """
    TEST 1: Login page verification
    - Navigates to /login.
    - Verifies page title and branding.
    - Asserts that identifier input, password input, role buttons, and submit button exist.
    """
    driver.get(f"{base_url}/login")
    wait = WebDriverWait(driver, 10)

    # 1. Verify Page Title
    assert "Login - StockSense AI" in driver.title, f"Unexpected page title: {driver.title}"

    # 2. Verify Login Form Container
    login_form = wait.until(EC.visibility_of_element_located((By.ID, "login-form")))
    assert login_form.is_displayed(), "Login form is not visible on page."

    # 3. Verify Username / Email Input Field
    identifier_input = driver.find_element(By.ID, "identifier")
    assert identifier_input.is_displayed(), "Identifier input field is not displayed."
    assert identifier_input.get_attribute("type") == "text", "Identifier input should be type 'text'."
    assert identifier_input.get_attribute("required") is not None, "Identifier field should have 'required' attribute."

    # 4. Verify Password Input Field
    password_input = driver.find_element(By.ID, "password")
    assert password_input.is_displayed(), "Password input field is not displayed."
    assert password_input.get_attribute("type") == "password", "Password input should be type 'password'."
    assert password_input.get_attribute("required") is not None, "Password field should have 'required' attribute."

    # 5. Verify Submit Button
    submit_btn = driver.find_element(By.ID, "login-submit-btn")
    assert submit_btn.is_displayed(), "Submit button is not displayed."
    assert "Sign In as User" in submit_btn.text, "Default submit button text should be 'Sign In as User'."

    # 6. Verify Role Selector Tabs
    user_tab = driver.find_element(By.ID, "tab-user-role")
    admin_tab = driver.find_element(By.ID, "tab-admin-role")
    assert user_tab.is_displayed() and admin_tab.is_displayed(), "Role selector tabs are not displayed."


def test_2_valid_user_login(driver, base_url):
    """
    TEST 2: Valid user authentication
    - Enters valid user credentials.
    - Submits login form.
    - Verifies successful authentication and redirect to /dashboard.
    """
    driver.get(f"{base_url}/login")
    wait = WebDriverWait(driver, 10)

    # 1. Locate form elements
    identifier_input = wait.until(EC.visibility_of_element_located((By.ID, "identifier")))
    password_input = driver.find_element(By.ID, "password")
    submit_btn = driver.find_element(By.ID, "login-submit-btn")

    # 2. Enter valid test user credentials
    identifier_input.clear()
    identifier_input.send_keys(TEST_USER_USERNAME)

    password_input.clear()
    password_input.send_keys(TEST_USER_PASSWORD)

    # 3. Submit the form
    submit_btn.click()

    # 4. Explicitly wait for redirection to user dashboard
    wait.until(EC.url_contains("/dashboard"))
    assert "/dashboard" in driver.current_url, f"Expected redirect to /dashboard, got {driver.current_url}"

    # 5. Verify authenticated dashboard content
    wait.until(EC.title_contains("Dashboard - StockSense AI"))
    page_source = driver.page_source
    assert ("Market Dashboard" in page_source or "StockSense AI" in driver.title), \
        "Authenticated user dashboard failed to render expected page elements."


def test_3_invalid_password_rejected(driver, base_url):
    """
    TEST 3: Invalid password handling
    - Enters a valid test username with an incorrect password.
    - Submits login form.
    - Verifies login rejection and display of the error message container.
    - Asserts session is not created and browser stays on /login.
    """
    driver.get(f"{base_url}/login")
    wait = WebDriverWait(driver, 10)

    identifier_input = wait.until(EC.visibility_of_element_located((By.ID, "identifier")))
    password_input = driver.find_element(By.ID, "password")
    submit_btn = driver.find_element(By.ID, "login-submit-btn")

    # Enter valid username with invalid password
    identifier_input.clear()
    identifier_input.send_keys(TEST_USER_USERNAME)

    password_input.clear()
    password_input.send_keys("WrongInvalidPassword!2026")

    submit_btn.click()

    # Wait for the error banner to appear
    error_alert = wait.until(EC.visibility_of_element_located((By.ID, "auth-error-alert")))
    assert error_alert.is_displayed(), "Error alert container was not displayed on invalid login."
    
    alert_text = error_alert.text.lower()
    assert ("invalid credentials" in alert_text or "failed" in alert_text or "verify" in alert_text), \
        f"Unexpected error message text: '{error_alert.text}'"

    # Verify user remains unauthenticated on the login page
    assert "/login" in driver.current_url, "User should remain on /login page after failed authentication."


def test_4_empty_login_fields_validation(driver, base_url):
    """
    TEST 4: Empty login fields validation
    - Submits the login form without entering credentials.
    - Verifies that client-side HTML5 constraint validation triggers or
      the form submission is blocked from navigating away.
    """
    driver.get(f"{base_url}/login")
    wait = WebDriverWait(driver, 10)

    identifier_input = wait.until(EC.visibility_of_element_located((By.ID, "identifier")))
    password_input = driver.find_element(By.ID, "password")
    submit_btn = driver.find_element(By.ID, "login-submit-btn")

    # Ensure fields are completely empty
    identifier_input.clear()
    password_input.clear()

    # Verify HTML5 required constraint validation
    is_identifier_valid = driver.execute_script("return arguments[0].checkValidity();", identifier_input)
    assert is_identifier_valid is False, "Empty identifier field should fail HTML5 constraint validation."

    # Click submit button
    submit_btn.click()

    # Short wait: verify URL does not change and user remains on /login
    time.sleep(1)
    assert "/login" in driver.current_url, "Form with empty required fields should not navigate away from /login."


def test_5_user_access_to_admin_page_denied(driver, base_url):
    """
    TEST 5: Standard user RBAC boundary enforcement
    - Authenticates as a standard user ('user' role).
    - Attempts to directly access protected administrative route /admin.
    - Verifies that access is strictly denied (renders 403 Forbidden page).
    """
    driver.get(f"{base_url}/login")
    wait = WebDriverWait(driver, 10)

    # 1. Log in as standard user
    identifier_input = wait.until(EC.visibility_of_element_located((By.ID, "identifier")))
    password_input = driver.find_element(By.ID, "password")
    submit_btn = driver.find_element(By.ID, "login-submit-btn")

    identifier_input.clear()
    identifier_input.send_keys(TEST_USER_USERNAME)
    password_input.clear()
    password_input.send_keys(TEST_USER_PASSWORD)
    submit_btn.click()

    wait.until(EC.url_contains("/dashboard"))

    # 2. Attempt unauthorized direct navigation to /admin
    driver.get(f"{base_url}/admin")

    # 3. Application RBAC check: Non-admin users are shown the 403 Forbidden template
    # Verify title or page content reflects 403 / Access Forbidden
    wait.until(lambda d: "403" in d.title or "Forbidden" in d.title or "Access Forbidden" in d.page_source)

    page_source = driver.page_source
    assert ("403" in driver.title or "Forbidden" in driver.title or "ACCESS FORBIDDEN" in page_source), \
        "Standard user was not blocked with 403 Forbidden when accessing /admin."

    assert ("Administrator Access Required" in page_source or "Access Forbidden" in page_source), \
        "403 Forbidden security template message was not displayed to standard user."


def test_6_admin_login_and_portal_access(driver, base_url):
    """
    TEST 6: Administrative login and RBAC verification
    - Selects the 'Admin Login' tab.
    - Enters authorized administrator credentials.
    - Submits authentication.
    - Verifies successful redirection to /admin and access to the Admin Portal.
    """
    driver.get(f"{base_url}/login")
    wait = WebDriverWait(driver, 10)

    # 1. Switch to Admin Login tab
    admin_tab = wait.until(EC.element_to_be_clickable((By.ID, "tab-admin-role")))
    admin_tab.click()

    # Verify submit button updates to 'Sign In as Admin'
    submit_btn = driver.find_element(By.ID, "login-submit-btn")
    wait.until(lambda d: "Sign In as Admin" in submit_btn.text)

    # 2. Enter administrator credentials
    identifier_input = driver.find_element(By.ID, "identifier")
    password_input = driver.find_element(By.ID, "password")

    identifier_input.clear()
    identifier_input.send_keys(TEST_ADMIN_USERNAME)
    password_input.clear()
    password_input.send_keys(TEST_ADMIN_PASSWORD)

    # 3. Submit admin login
    submit_btn.click()

    # 4. Verify redirection to Admin Portal
    wait.until(EC.url_contains("/admin"))
    assert "/admin" in driver.current_url, f"Expected redirect to /admin, got {driver.current_url}"

    # 5. Verify Admin Portal title and landing page content
    wait.until(EC.title_contains("Admin Portal - StockSense AI"))
    page_source = driver.page_source
    assert ("Admin Portal" in page_source or "StockSense AI" in driver.title), \
        "Admin Portal failed to display authenticated administrator workspace."
