# StockSense AI — Performance Test Results Report

## 1. Test Overview & Execution Status

- **Project**: StockSense AI — Indian Stock Analysis & Paper Trading Platform
- **Test Artifact**: `tests/performance/StockSense_AI_Performance_Test.jmx`
- **Target Endpoint**: Safe HTTP GET `/login`
- **Concurrency Setup**: 10 Concurrent Virtual Users, 5-second Ramp-up, 5 Loops (50 Total Samples)
- **Status in Current Workspace**: **EXECUTED SUCCESSFULLY**
- **Execution Date**: 16 October 2026

---

## 2. Environment Specifications

| Component | Specification |
| :--- | :--- |
| **Operating System** | Windows 10/11 64-bit |
| **Java Runtime** | Java SE Runtime Environment `build 24.0.1+9-30` (Detected & Verified) |
| **Testing Tool** | Apache JMeter 5.6.3 (`C:\Users\ramir\Downloads\apache-jmeter-5.6.3\apache-jmeter-5.6.3\bin\jmeter.bat`) |
| **Application Server** | Flask 3.0.3 / Werkzeug 3.1.8 |
| **Target URL** | `http://127.0.0.1:5000/login` |
| **Database Engine** | SQLite 3 (`stocksense.db` — strictly read-only execution) |

---

## 3. Actual Benchmark Metrics (Executed Live)

The performance test was executed against the running StockSense AI Flask server using Apache JMeter 5.6.3. All 50 requests completed with 0 errors.

| Sample Label | # Samples | Average (ms) | Min (ms) | Max (ms) | Throughput (req/s) | Error % | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **HTTP GET - Safe Route (/login)** | **50** | **6 ms** | **4 ms** | **56 ms** | **11.0 req/s** | **0.00%** | **PASS** |
| **TOTAL** | **50** | **6 ms** | **4 ms** | **56 ms** | **11.0 req/s** | **0.00%** | **PASS** |

### JMeter Execution Log Output:
```text
Creating summariser <summary>
Created the tree successfully using tests/performance/StockSense_AI_Performance_Test.jmx
Starting standalone test @ 2026 Oct 16 16:51:59 GMT+05:30
Waiting for possible Shutdown/StopTestNow/HeapDump/ThreadDump message on port 4445
summary +      1 in 00:00:00 =    4.0/s Avg:    56 Min:    56 Max:    56 Err:     0 (0.00%) Active: 1 Started: 1 Finished: 0
summary +     49 in 00:00:04 =   11.4/s Avg:     5 Min:     4 Max:     9 Err:     0 (0.00%) Active: 0 Started: 10 Finished: 10
summary =     50 in 00:00:05 =   11.0/s Avg:     6 Min:     4 Max:    56 Err:     0 (0.00%)
Tidying up ...    @ 2026 Oct 16 16:52:04 GMT+05:30
... end of run
```

---

## 4. How to Open and View Results in JMeter

### Step 1: Open the Test Plan in JMeter GUI
In JMeter, go to **File → Open** and select:
`C:\Users\ramir\Downloads\apache-jmeter-5.6.3\apache-jmeter-5.6.3\StockSense_AI_Performance_Test.jmx`  
*(or browse to `c:\Users\ramir\OneDrive\Documents\STOCKSENSE_AI\tests\performance\StockSense_AI_Performance_Test.jmx`)*

### Step 2: Load the Captured Data
1. Click on **Summary Report** or **Aggregate Report** in the left sidebar.
2. In the **Filename** input box at the top, click **Browse...**.
3. Select `c:\Users\ramir\OneDrive\Documents\STOCKSENSE_AI\tests\performance\results.jtl`.
4. JMeter will populate the complete metrics table showing all 50 samples, average (6 ms), min (4 ms), max (56 ms), and 0% errors!

### Step 3: Open the Interactive HTML Report
An interactive HTML dashboard with response graphs has already been generated:
Open in any browser:
`c:\Users\ramir\OneDrive\Documents\STOCKSENSE_AI\tests\performance\html_report\index.html`

---

## 5. Metric Interpretation Guide for Viva / Faculty Evaluation

When explaining the performance results to your college faculty:

### 1. Average Response Time: **6 ms**
- **Meaning**: On average, the Flask server processed and returned the `/login` page in just 6 milliseconds.
- **Evaluation**: Extremely fast, well below the standard 200 ms benchmark for local web applications.

### 2. Min & Max Latency: **4 ms & 56 ms**
- **Min Response Time (4 ms)**: Reflects warm cache performance when the Jinja2 template and route handler are pre-compiled in memory.
- **Max Response Time (56 ms)**: Occurred on the initial connection handshake and first request.

### 3. Throughput: **11.0 requests per second**
- **Meaning**: With 10 concurrent virtual users ramped up over 5 seconds, the single-threaded development server served 11 full HTTP requests each second smoothly.

### 4. Error Rate: **0.00%**
- **Meaning**: All 50 requests returned HTTP status 200 OK and passed the response text validation assertions. Zero connection drops or server errors occurred.

---

## 6. Screenshots to Present to Your College Faculty

1. **JMeter Summary Report**:
   - Screenshot showing the **Summary Report** in JMeter with the 50 samples and 6 ms average latency.
2. **JMeter View Results Tree**:
   - Screenshot showing the green checkmarks for all HTTP GET requests.
3. **Interactive HTML Dashboard**:
   - Screenshot of `tests/performance/html_report/index.html` showing the response time chart and 100% success pie chart.
