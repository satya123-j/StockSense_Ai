# StockSense AI — Non-Functional Performance Testing Documentation (Apache JMeter)

## 1. Objective of Non-Functional Testing
While **functional testing** verifies *what* the application does (features, authentication, access control), **non-functional testing** measures *how well* the application behaves under load. 

For **StockSense AI**, non-functional performance testing evaluates:
1. **Response Time / Latency**: How quickly the server returns web pages and analytics to concurrent users.
2. **Throughput**: The number of requests the Flask application can process per second.
3. **Error Rate**: Whether any requests fail, drop connection, or encounter HTTP 5xx errors under concurrent access.
4. **Stability & Concurrency Handling**: How the Python WSGI server behaves when multiple users hit the platform simultaneously.

---

## 2. Testing Tool: Apache JMeter

**Apache JMeter™** is a standard open-source load-testing and performance benchmarking tool designed to measure the performance of web applications and APIs.

- **Official Download URL**: [https://jmeter.apache.org/download_jmeter.cgi](https://jmeter.apache.org/download_jmeter.cgi)
- **Binary Package Required**: `apache-jmeter-5.6.3.zip` (Binaries)
- **Runtime Dependency**: Java Runtime Environment (JRE) / Java Development Kit (JDK) 8 or higher.

### Environment Audit on This System
- **Java Check**: `java version "24.0.1"` is **Installed and Verified**.
- **JMeter Check**: Apache JMeter binary is not yet pre-installed in the local PATH. Follow the setup steps below to run the test plan.

---

## 3. Step-by-Step Apache JMeter Installation on Windows

To install and run Apache JMeter on Windows:

1. **Download Binary Archive**:
   - Visit the official download page: [https://jmeter.apache.org/download_jmeter.cgi](https://jmeter.apache.org/download_jmeter.cgi)
   - Under **Binaries**, download the zip archive: `apache-jmeter-5.6.3.zip`.
2. **Extract Archive**:
   - Extract the downloaded `.zip` file to a convenient local folder, for example:
     `C:\apache-jmeter-5.6.3\`
3. **Verify Java Execution**:
   - Open PowerShell and confirm Java is ready:
     ```powershell
     java -version
     ```
4. **Launch JMeter GUI**:
   - Navigate to the `bin/` folder inside the extracted directory and run `jmeter.bat`:
     ```powershell
     cd C:\apache-jmeter-5.6.3\bin
     .\jmeter.bat
     ```
   - The graphical Apache JMeter workbench will open.

---

## 4. Test Plan Architecture (`StockSense_AI_Performance_Test.jmx`)

The test plan is stored at:
`tests/performance/StockSense_AI_Performance_Test.jmx`

### Design Principles & Safety Rules
- **Safe Read-Only GET Endpoint**: Uses the verified `/login` endpoint. It exercises the Flask router, Jinja2 template engine, and HTTP stack **without modifying the database, virtual wallets, or user records**.
- **No Heavy Mutations**: Does not execute destructive POST requests, buying/selling stocks, or database resets.
- **Dynamic Configuration**: Server host, port, and endpoint are parameterised via User Defined Variables with property overrides (`${__P(host,127.0.0.1)}`, `${__P(port,5000)}`, `${__P(path,/login)}`).

### Test Configuration Parameters
| Parameter | Value | Rationale |
| :--- | :--- | :--- |
| **Target Host** | `127.0.0.1` | Local development test server |
| **Target Port** | `5000` (Configurable) | Flask standard listening port |
| **Target Endpoint** | `/login` | Verified safe, lightweight public GET route |
| **Number of Threads (Users)**| `10` | Simulates 10 concurrent virtual investors |
| **Ramp-Up Period** | `5 seconds` | Simulates realistic user arrival (2 new users per second) |
| **Loop Count** | `5 loops` | Each virtual user performs 5 repeated visits |
| **Total Test Samples** | `10 users * 5 loops = 50 requests` | Clean, controlled baseline dataset |

### Elements Configured in the Test Plan
1. **Thread Group**: `StockSense Concurrent Users (10 Threads)`
2. **HTTP Header Manager**: Specifies `Accept` and custom `User-Agent` (`ApacheJMeter-StockSenseAI-TestRunner`).
3. **HTTP Request Sampler**: Performs `GET http://${HOST}:${PORT}${ENDPOINT}`.
4. **Response Assertions**:
   - **HTTP Status 200 Assertion**: Validates that the response code is exactly `200`.
   - **Content Assertion**: Validates that the response HTML contains the string `"StockSense AI"`.
5. **Listeners**:
   - **Summary Report**: Tabulates average latency, min/max, throughput, and error rates.
   - **Aggregate Report**: Shows percentile distributions (90%, 95%, 99%).
   - **View Results Tree**: Displays individual request/response headers and bodies for debugging.

---

## 5. How to Execute the JMeter Plan

### Prerequisite: Start the StockSense AI Application
Ensure the Flask server is running before starting the performance test:
```powershell
cd c:\Users\ramir\OneDrive\Documents\STOCKSENSE_AI
python run.py
```
*(Server will start at `http://127.0.0.1:5000`)*

---

### Method A: Graphical Interface (GUI Mode) — Recommended for Faculty Demonstrations
1. Open Apache JMeter (`jmeter.bat`).
2. Go to **File → Open** (or press `Ctrl + O`).
3. Browse to and select:
   `c:\Users\ramir\OneDrive\Documents\STOCKSENSE_AI\tests\performance\StockSense_AI_Performance_Test.jmx`
4. Expand the tree in the left sidebar:
   - Click on **Summary Report** or **Aggregate Report**.
5. Click the green **Start** button (▶) on the top toolbar to execute the load test.
6. Watch the real-time sample counter and response times update live.

---

### Method B: Non-GUI / Command-Line Mode (CLI Mode) — For Automated Benchmarks
Run the test from PowerShell without GUI overhead:
```powershell
# Navigate to JMeter bin directory
cd C:\apache-jmeter-5.6.3\bin

# Execute headless load test and output results to CSV
.\jmeter.bat -n -t "c:\Users\ramir\OneDrive\Documents\STOCKSENSE_AI\tests\performance\StockSense_AI_Performance_Test.jmx" -l "c:\Users\ramir\OneDrive\Documents\STOCKSENSE_AI\tests\performance\results.jtl" -e -o "c:\Users\ramir\OneDrive\Documents\STOCKSENSE_AI\tests\performance\html_report"
```

To run against a different port (e.g., port 5001):
```powershell
.\jmeter.bat -n -t "c:\Users\ramir\OneDrive\Documents\STOCKSENSE_AI\tests\performance\StockSense_AI_Performance_Test.jmx" -Jport=5001 -l "c:\Users\ramir\OneDrive\Documents\STOCKSENSE_AI\tests\performance\results.jtl"
```

---

## 6. How to Interpret Performance Metrics

When presenting the test metrics to your faculty, explain these standard metrics:

| Metric | Definition | Good / Desirable Target |
| :--- | :--- | :--- |
| **Average Response Time (ms)** | Arithmetic mean time from request dispatch to complete response reception. | `< 200 ms` for local web apps; `< 500 ms` under load |
| **Min / Max Response Time (ms)**| Fastest and slowest individual request recorded during the run. | Max should not spike excessively above average |
| **90th / 95th Percentile (ms)** | 90% or 95% of all requests completed faster than this time. Eliminates outliers. | `< 300 ms` |
| **Throughput (req/sec)** | Number of complete HTTP transactions the server handles per second. | Higher is better (typically `20 - 80 req/s` for single-process Flask) |
| **Error Percentage (%)** | Percentage of requests that failed assertions or returned HTTP 4xx/5xx status. | **`0.00%`** is the target |
| **Network Received KB/sec** | Volume of HTTP payload received from the server per second. | Depends on page HTML and asset sizes |

---

## 7. Faculty Presentation Talking Points
1. **Why JMeter?**: Explain that JMeter is an industry-standard load testing tool used in financial institutions and software enterprises to stress-test APIs.
2. **Why 10 Users / 5 Loops?**: Emphasize that this provides a **clean baseline benchmark** suitable for a college project evaluation without overloading the local student machine.
3. **Safety First**: Point out that the load test was specifically targeted at a safe, read-only GET endpoint (`/login`), guaranteeing zero risk of database corruption or duplicate transaction spam.
