/**
 * StockSense AI - Real-time Stock Analysis & Technical Indicator Engine (Light Mode)
 */

let mainPriceChart = null;
let rsiChart = null;
let macdChart = null;

let currentSymbol = 'TCS';
let currentRange = '1m';
let historyDataCache = {};
let technicalsCache = {};
let isSavedInWatchlist = false;
let latestStockQuote = null;

// Moving average overlay state for main price chart
let showSMA20 = true;
let showSMA50 = true;

document.addEventListener('DOMContentLoaded', () => {
  // 1. Extract symbol from path /analysis/<symbol> or query string ?symbol=...
  const pathParts = window.location.pathname.split('/');
  if (pathParts.length >= 3 && pathParts[2]) {
    currentSymbol = decodeURIComponent(pathParts[2]).replace('.NS', '').replace('.BO', '').toUpperCase();
  } else {
    const symbolParam = new URLSearchParams(window.location.search).get('symbol');
    if (symbolParam) currentSymbol = symbolParam.replace('.NS', '').replace('.BO', '').toUpperCase();
  }

  // 2. Setup Controls & Listeners
  setupInPageSearch();
  setupQuickStockChips();
  setupTimeframeButtons();
  setupOverlayToggles();
  setupWatchlistToggle();
  setupInPagePaperTrade();
  setupPaperTradeModal();
  setupPaperTradeSellModal();
  loadMarketSessionStatus();

  // 3. Initialize Stock Details
  initAnalysisPage();
});

// Setup In-Page Search Bar
function setupInPageSearch() {
  if (typeof setupSearchAutocomplete === 'function') {
    setupSearchAutocomplete('analysis-page-search-input', 'analysis-page-search-results', (stock) => {
      if (stock && stock.symbol) {
        switchToStock(stock.symbol);
      }
    });
  }
}

// Setup Popular Stock Chips
function setupQuickStockChips() {
  const chips = document.querySelectorAll('.quick-stock-chip');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const sym = chip.getAttribute('data-symbol');
      if (sym) switchToStock(sym);
    });
  });
}

// Setup MA Overlay Toggles on Price Chart
function setupOverlayToggles() {
  const btn20 = document.getElementById('toggle-sma20-btn');
  const btn50 = document.getElementById('toggle-sma50-btn');

  if (btn20) {
    btn20.addEventListener('click', () => {
      showSMA20 = !showSMA20;
      btn20.classList.toggle('active', showSMA20);
      if (mainPriceChart && mainPriceChart.data.datasets.length > 1) {
        mainPriceChart.data.datasets[1].hidden = !showSMA20;
        mainPriceChart.update();
      }
    });
  }

  if (btn50) {
    btn50.addEventListener('click', () => {
      showSMA50 = !showSMA50;
      btn50.classList.toggle('active', showSMA50);
      if (mainPriceChart && mainPriceChart.data.datasets.length > 2) {
        mainPriceChart.data.datasets[2].hidden = !showSMA50;
        mainPriceChart.update();
      }
    });
  }
}

// Switch stock without full page reload
function switchToStock(symbol) {
  if (!symbol) return;
  currentSymbol = symbol.trim().toUpperCase();
  historyDataCache = {};
  technicalsCache = {};

  // Notify components (e.g. Chatbot) of symbol change
  window.dispatchEvent(new CustomEvent('stocksense:symbolChange', { detail: { symbol: currentSymbol } }));

  // Update browser URL without reload
  const newUrl = `/analysis/${encodeURIComponent(currentSymbol)}`;

  window.history.pushState({ symbol: currentSymbol }, '', newUrl);

  // Update Quick Chip active state
  document.querySelectorAll('.quick-stock-chip').forEach(chip => {
    if (chip.getAttribute('data-symbol') === currentSymbol) {
      chip.classList.add('active');
    } else {
      chip.classList.remove('active');
    }
  });

  // Clear any existing paper trade alerts
  const bErr = document.getElementById('pt-buy-error-alert');
  const bSucc = document.getElementById('pt-buy-success-alert');
  const sErr = document.getElementById('pt-sell-error-alert');
  const sSucc = document.getElementById('pt-sell-success-alert');
  if (bErr) bErr.style.display = 'none';
  if (bSucc) bSucc.style.display = 'none';
  if (sErr) sErr.style.display = 'none';
  if (sSucc) sSucc.style.display = 'none';

  initAnalysisPage();
}

// Listen to browser Back/Forward navigation
window.addEventListener('popstate', (e) => {
  const pathParts = window.location.pathname.split('/');
  if (pathParts.length >= 3 && pathParts[2]) {
    currentSymbol = decodeURIComponent(pathParts[2]).replace('.NS', '').replace('.BO', '').toUpperCase();
    historyDataCache = {};
    technicalsCache = {};
    initAnalysisPage();
  }
});

async function initAnalysisPage() {
  // Update header symbol immediately
  const symbolElem = document.getElementById('stock-symbol-text');
  if (symbolElem) symbolElem.textContent = currentSymbol;

  // Reset UI loading states
  setGlobalLoadingState(true);
  hideInvalidSymbolAlert();

  try {
    const quoteSuccess = await loadOverviewAndStats();
    if (quoteSuccess) {
      await Promise.allSettled([
        loadTechnicalAnalysis(),
        loadPriceChart(currentRange),
        checkWatchlistState(),
        loadUserStockHolding(),
        loadMLPrediction(),
        loadAIRecommendation()
      ]);
      if (typeof updatePaperTradeSection === 'function') {
        await updatePaperTradeSection();
      }
    }
  } catch (err) {
    console.error('Error initializing analysis page:', err);
  } finally {
    setGlobalLoadingState(false);
  }
}

function setGlobalLoadingState(isLoading) {
  const priceElem = document.getElementById('stock-price-text');
  if (isLoading && priceElem) {
    priceElem.innerHTML = `<span class="spinner-border spinner-border-sm text-danger me-1" role="status"></span> Loading...`;
  }
}

function showInvalidSymbolAlert(message) {
  const alert = document.getElementById('invalid-symbol-alert');
  const alertDesc = document.getElementById('invalid-symbol-alert-desc');
  if (alert) {
    if (alertDesc) {
      alertDesc.textContent = message || `Security symbol "${currentSymbol}" was not found on Indian Stock Exchanges (NSE/BSE).`;
    }
    alert.style.display = 'flex';
  }
  
  // Clear displays
  const priceElem = document.getElementById('stock-price-text');
  if (priceElem) priceElem.textContent = 'Symbol Not Found';
  const deltaElem = document.getElementById('stock-delta-badge');
  if (deltaElem) {
    deltaElem.className = 'delta-pill neutral num-mono';
    deltaElem.textContent = '--';
  }
  const compElem = document.getElementById('stock-company-text');
  if (compElem) compElem.textContent = `No listed security found for "${currentSymbol}"`;

  setTechnicalsNotAvailable();
  destroyAllCharts();
}

function hideInvalidSymbolAlert() {
  const alert = document.getElementById('invalid-symbol-alert');
  if (alert) alert.style.display = 'none';
}

function destroyAllCharts() {
  if (mainPriceChart) {
    mainPriceChart.destroy();
    mainPriceChart = null;
  }
  if (rsiChart) {
    rsiChart.destroy();
    rsiChart = null;
  }
  if (macdChart) {
    macdChart.destroy();
    macdChart = null;
  }
}

// 1. Fetch Market Session Status (IST Trading Hours)
async function loadMarketSessionStatus() {
  const pill = document.getElementById('market-session-pill');
  if (!pill) return;

  try {
    const res = await API.request('/api/market/status');
    if (res && res.data) {
      const status = res.data;
      if (status.is_market_open) {
        pill.className = 'stock-card-badge';
        pill.style.color = '#15803d';
        pill.style.borderColor = 'rgba(22,163,74,0.3)';
        pill.style.backgroundColor = 'rgba(22,163,74,0.08)';
        pill.textContent = 'Market: LIVE (09:15 - 15:30 IST)';
      } else {
        pill.className = 'stock-card-badge';
        pill.style.color = '#4b5563';
        pill.style.borderColor = 'rgba(107,114,128,0.3)';
        pill.style.backgroundColor = '#f1f5f9';
        pill.textContent = `Market: ${status.session_name}`;
      }
    }
  } catch (e) {
    console.warn('Market status fetch warning:', e);
  }
}

// 2. Load Real Market Overview & Statistics
async function loadOverviewAndStats() {
  const priceElem = document.getElementById('stock-price-text');
  const alertBox = document.getElementById('data-source-alert');
  const alertTitle = document.getElementById('data-source-alert-title');
  const alertDesc = document.getElementById('data-source-alert-desc');
  const alertBadge = document.getElementById('data-source-alert-badge');

  try {
    const res = await API.request(`/api/stocks/${encodeURIComponent(currentSymbol)}/quote`);
    if (!res || !res.data) {
      throw new Error(`Real market data for ${currentSymbol} could not be retrieved.`);
    }

    const data = res.data;
    latestStockQuote = data;
    hideInvalidSymbolAlert();

    // Header
    document.getElementById('stock-symbol-text').textContent = data.symbol;
    document.getElementById('stock-company-text').textContent = data.name || data.symbol;
    document.getElementById('stock-exchange-badge').textContent = data.exchange || 'NSE';

    if (data.current_price !== null && data.current_price !== undefined) {
      priceElem.textContent = formatINR(data.current_price);
      
      const changeVal = Number(data.change) || 0;
      const changePctVal = Number(data.change_percent) || 0;
      const isPos = (changeVal >= 0);
      const deltaElem = document.getElementById('stock-delta-badge');
      deltaElem.className = `delta-pill ${isPos ? 'positive' : 'negative'} num-mono`;
      deltaElem.innerHTML = `${isPos ? '▲' : '▼'} ${formatINR(Math.abs(changeVal))} (${formatPercent(changePctVal)})`;
    } else {
      priceElem.textContent = 'Price Unavailable';
      document.getElementById('stock-delta-badge').textContent = '--';
    }

    // Data Source Badge & Alert Notice
    const sourcePill = document.getElementById('data-source-pill');
    if (sourcePill) {
      sourcePill.textContent = `Data Source: ${data.data_source || 'Upstox Developer API v2'}`;
    }

    if (alertBox) {
      if (data.data_source && data.data_source.includes('Upstox Developer API')) {
        alertBox.style.display = 'flex';
        alertTitle.textContent = 'Official Upstox Developer API Active';
        alertDesc.textContent = 'Streaming live market quotes directly from official Upstox API v2.';
        alertBadge.textContent = 'Upstox v2';
        alertBadge.style.color = '#e53935';
      } else if (data.data_source && data.data_source.includes('Pending in .env')) {
        alertBox.style.display = 'flex';
        alertTitle.textContent = 'Live NSE/BSE Feed Active';
        alertDesc.textContent = 'To enable direct Upstox streaming, configure UPSTOX_ACCESS_TOKEN in your local .env file.';
        alertBadge.textContent = 'NSE/BSE Feed';
        alertBadge.style.color = '#2563eb';
      } else if (data.data_source && data.data_source.includes('Not Configured')) {
        alertBox.style.display = 'flex';
        alertTitle.textContent = 'Market API Not Configured';
        alertDesc.textContent = 'Set UPSTOX_ACCESS_TOKEN in your .env file to enable live market streaming.';
        alertBadge.textContent = 'Setup Required';
        alertBadge.style.color = '#d97706';
      } else {
        alertBox.style.display = 'none';
      }
    }

    // Timestamp
    const tsElem = document.getElementById('stock-timestamp-text');
    if (tsElem) {
      tsElem.textContent = `Last Data Update: ${data.timestamp || 'Live Feed'}`;
    }

    // Market Statistics Grid
    document.getElementById('metric-open').textContent = data.open ? formatINR(data.open) : 'N/A';
    document.getElementById('metric-prev-close').textContent = data.previous_close ? formatINR(data.previous_close) : 'N/A';
    document.getElementById('metric-day-high').textContent = data.day_high ? formatINR(data.day_high) : 'N/A';
    document.getElementById('metric-day-low').textContent = data.day_low ? formatINR(data.day_low) : 'N/A';
    document.getElementById('metric-volume').textContent = data.volume ? Number(data.volume).toLocaleString('en-IN') : 'N/A';
    document.getElementById('metric-mcap').textContent = formatLargeINR(data.market_cap);
    document.getElementById('metric-52w-high').textContent = data.fifty_two_week_high ? formatINR(data.fifty_two_week_high) : 'N/A';
    document.getElementById('metric-52w-low').textContent = data.fifty_two_week_low ? formatINR(data.fifty_two_week_low) : 'N/A';

    // Profile & Sector
    document.getElementById('metric-sector').textContent = `Sector: ${data.sector || 'Indian Equity'}`;
    document.getElementById('metric-industry').textContent = `Industry: ${data.industry || 'NSE Listed'}`;
    document.getElementById('stock-description').textContent = data.description || `${data.name || data.symbol} is an equity security listed on the National Stock Exchange of India (NSE).`;

    if (typeof updatePaperTradeSection === 'function') {
      updatePaperTradeSection();
    }

    return true;
  } catch (err) {
    console.error('Error loading stock quote:', err);
    showInvalidSymbolAlert(err.message || `Security "${currentSymbol}" not found.`);
    return false;
  }
}

// 3. Load Real Technical Analysis Indicators (RSI, MACD, Moving Averages)
async function loadTechnicalAnalysis() {
  try {
    const res = await API.request(`/api/stocks/${encodeURIComponent(currentSymbol)}/technical-analysis?period=1y`);
    
    if (!res || !res.data || res.data.error) {
      setTechnicalsNotAvailable();
      return;
    }

    const tech = res.data;
    technicalsCache[currentSymbol] = tech;

    const latest = tech.latest || {};
    const summary = tech.summary_indicators || {};

    const tsElem = document.getElementById('technicals-timestamp-text');
    if (tsElem) {
      tsElem.textContent = `Calculated at ${tech.timestamp || 'Latest market close'}`;
    }

    // 1. RSI Card (Latest 14-period)
    const rsiVal = latest.rsi !== undefined && latest.rsi !== null ? latest.rsi : summary.rsi_14;
    if (rsiVal !== undefined && rsiVal !== null) {
      document.getElementById('rsi-value-display').textContent = Number(rsiVal).toFixed(2);
      
      const rsiBadge = document.getElementById('rsi-status-badge');
      const rsiMomentum = document.getElementById('rsi-momentum-text');
      
      if (rsiVal >= 70) {
        rsiBadge.className = 'tech-badge-status delta-pill negative';
        rsiBadge.textContent = 'Overbought';
        rsiMomentum.textContent = 'Overbought (> 70.00)';
      } else if (rsiVal <= 30) {
        rsiBadge.className = 'tech-badge-status delta-pill positive';
        rsiBadge.textContent = 'Oversold';
        rsiMomentum.textContent = 'Oversold (< 30.00)';
      } else {
        rsiBadge.className = 'tech-badge-status delta-pill neutral';
        rsiBadge.textContent = 'Neutral';
        rsiMomentum.textContent = rsiVal >= 50 ? 'Positive Momentum (> 50)' : 'Negative Momentum (< 50)';
      }
    } else {
      document.getElementById('rsi-value-display').textContent = 'N/A';
      document.getElementById('rsi-status-badge').textContent = 'N/A';
      document.getElementById('rsi-momentum-text').textContent = 'N/A';
    }

    // 2. MACD Card (12, 26, 9)
    const macdVal = latest.macd !== undefined && latest.macd !== null ? latest.macd : summary.macd;
    const signalVal = latest.macd_signal !== undefined && latest.macd_signal !== null ? latest.macd_signal : summary.macd_signal;
    const histVal = latest.macd_histogram !== undefined && latest.macd_histogram !== null ? latest.macd_histogram : summary.macd_hist;

    if (macdVal !== undefined && signalVal !== undefined && macdVal !== null) {
      document.getElementById('macd-value-display').textContent = histVal !== null ? (histVal > 0 ? `+${Number(histVal).toFixed(2)}` : Number(histVal).toFixed(2)) : '--';
      document.getElementById('macd-line-val').textContent = Number(macdVal).toFixed(2);
      document.getElementById('macd-signal-val').textContent = Number(signalVal).toFixed(2);

      const macdBadge = document.getElementById('macd-status-badge');
      const macdCross = document.getElementById('macd-crossover-text');

      if (macdVal >= signalVal) {
        macdBadge.className = 'tech-badge-status delta-pill positive';
        macdBadge.textContent = 'MACD > Signal';
        macdCross.textContent = `MACD (${Number(macdVal).toFixed(2)}) > Signal (${Number(signalVal).toFixed(2)})`;
      } else {
        macdBadge.className = 'tech-badge-status delta-pill negative';
        macdBadge.textContent = 'MACD < Signal';
        macdCross.textContent = `MACD (${Number(macdVal).toFixed(2)}) < Signal (${Number(signalVal).toFixed(2)})`;
      }
    } else {
      document.getElementById('macd-value-display').textContent = 'N/A';
      document.getElementById('macd-line-val').textContent = 'N/A';
      document.getElementById('macd-signal-val').textContent = 'N/A';
      document.getElementById('macd-status-badge').textContent = 'N/A';
      document.getElementById('macd-crossover-text').textContent = 'N/A';
    }

    // 3. Moving Average Card (MA20, MA50, EMA20)
    const ma20Val = latest.ma_20 !== undefined && latest.ma_20 !== null ? latest.ma_20 : summary.sma_20;
    const ma50Val = latest.ma_50 !== undefined && latest.ma_50 !== null ? latest.ma_50 : summary.sma_50;
    const ema20Val = summary.ema_20;

    if (ma20Val !== undefined && ma20Val !== null) {
      document.getElementById('ma-sma20-val').textContent = formatINR(ma20Val);
      document.getElementById('ma-sma50-val').textContent = ma50Val ? formatINR(ma50Val) : 'N/A';
      document.getElementById('ma-ema20-val').textContent = ema20Val ? formatINR(ema20Val) : 'N/A';

      const maBadge = document.getElementById('ma-status-badge');
      const maTrend = document.getElementById('ma-trend-text');

      if (ma50Val && ma20Val >= ma50Val) {
        maBadge.className = 'tech-badge-status delta-pill positive';
        maBadge.textContent = 'MA20 > MA50';
        maTrend.textContent = 'Short-term above Medium-term';
      } else if (ma50Val && ma20Val < ma50Val) {
        maBadge.className = 'tech-badge-status delta-pill negative';
        maBadge.textContent = 'MA20 < MA50';
        maTrend.textContent = 'Short-term below Medium-term';
      } else {
        maBadge.className = 'tech-badge-status delta-pill neutral';
        maBadge.textContent = 'Neutral';
        maTrend.textContent = 'Consolidation';
      }
    } else {
      document.getElementById('ma-sma20-val').textContent = 'N/A';
      document.getElementById('ma-sma50-val').textContent = 'N/A';
      document.getElementById('ma-ema20-val').textContent = 'N/A';
      document.getElementById('ma-status-badge').textContent = 'N/A';
      document.getElementById('ma-trend-text').textContent = 'N/A';
    }

    // Render Dedicated RSI & MACD Sub-Charts
    const series = tech.chart_series || tech.series || [];
    if (series && series.length > 0) {
      renderRSIChart(series);
      renderMACDChart(series);
    }

  } catch (err) {
    console.error('Error fetching technical indicators:', err);
    setTechnicalsNotAvailable();
  }
}

function setTechnicalsNotAvailable() {
  const elements = [
    'rsi-value-display', 'rsi-status-badge', 'rsi-momentum-text',
    'macd-value-display', 'macd-line-val', 'macd-signal-val', 'macd-status-badge', 'macd-crossover-text',
    'ma-sma20-val', 'ma-sma50-val', 'ma-ema20-val', 'ma-status-badge', 'ma-trend-text'
  ];
  elements.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = 'N/A';
  });

  if (rsiChart) {
    rsiChart.destroy();
    rsiChart = null;
  }
  if (macdChart) {
    macdChart.destroy();
    macdChart = null;
  }
}

// 4. Load Historical Price Chart (with SMA 20 & SMA 50 Overlays)
async function loadPriceChart(range) {
  currentRange = range;
  const overlay = document.getElementById('chart-loading-overlay');
  const emptyState = document.getElementById('chart-empty-state');
  const loadingText = document.getElementById('chart-loading-text');

  if (emptyState) emptyState.style.setProperty('display', 'none', 'important');
  if (overlay) {
    if (loadingText) loadingText.textContent = `Fetching historical ${range.toUpperCase()} candle data...`;
    overlay.style.setProperty('display', 'flex', 'important');
  }

  try {
    let history = historyDataCache[range];
    if (!history || !history.points || history.points.length === 0) {
      const res = await API.request(`/api/stocks/${encodeURIComponent(currentSymbol)}/history?range=${range}`);
      if (res && res.data && res.data.points && res.data.points.length > 0) {
        history = res.data;
        historyDataCache[range] = history;
      } else {
        history = (res && res.data) ? res.data : null;
      }
    }

    // Discard stale responses if user switched timeframes while request was in-flight
    if (currentRange !== range) return;

    if (!history || !history.points || history.points.length === 0) {
      const canvas = document.getElementById('mainPriceChartCanvas');
      if (canvas) {
        const existing = Chart.getChart(canvas);
        if (existing) existing.destroy();
      }
      if (mainPriceChart) {
        try { mainPriceChart.destroy(); } catch (e) {}
        mainPriceChart = null;
      }
      if (emptyState) emptyState.style.setProperty('display', 'flex', 'important');
      return;
    }

    renderMainPriceChart(history.points);

  } catch (err) {
    console.error('Error loading historical chart data:', err);
    if (currentRange === range) {
      const canvas = document.getElementById('mainPriceChartCanvas');
      if (canvas) {
        const existing = Chart.getChart(canvas);
        if (existing) existing.destroy();
      }
      if (mainPriceChart) {
        try { mainPriceChart.destroy(); } catch (e) {}
        mainPriceChart = null;
      }
      if (emptyState) emptyState.style.setProperty('display', 'flex', 'important');
    }
  } finally {
    if (overlay && currentRange === range) {
      overlay.style.setProperty('display', 'none', 'important');
    }
  }
}

// Render Main Price Chart with Moving Average Overlays (Light Mode)
function renderMainPriceChart(points) {
  const canvas = document.getElementById('mainPriceChartCanvas');
  if (!canvas) return;

  const emptyState = document.getElementById('chart-empty-state');
  if (emptyState) emptyState.style.setProperty('display', 'none', 'important');

  // Sanitize points to ensure numeric valid prices
  const validPoints = (points || []).filter(p => {
    if (!p || !p.date) return false;
    const c = Number(p.close);
    return !isNaN(c) && isFinite(c) && c > 0;
  });

  if (validPoints.length === 0) {
    if (emptyState) emptyState.style.setProperty('display', 'flex', 'important');
    return;
  }

  const labels = validPoints.map(p => String(p.date));
  const prices = validPoints.map(p => Number(p.close));

  // Determine overall price direction for chart coloring
  const isPositive = prices.length >= 2 ? (prices[prices.length - 1] >= prices[0]) : true;
  const lineColor = isPositive ? '#16a34a' : '#e53935';

  // Compute rolling SMA 20 & SMA 50 for overlay
  const sma20Series = [];
  const sma50Series = [];

  for (let i = 0; i < prices.length; i++) {
    // 20-period SMA
    if (i >= 19) {
      const slice20 = prices.slice(i - 19, i + 1);
      const sum20 = slice20.reduce((a, b) => a + b, 0);
      sma20Series.push(Number((sum20 / 20).toFixed(2)));
    } else {
      const slice20 = prices.slice(0, i + 1);
      const sum20 = slice20.reduce((a, b) => a + b, 0);
      sma20Series.push(Number((sum20 / (i + 1)).toFixed(2)));
    }

    // 50-period SMA
    if (i >= 49) {
      const slice50 = prices.slice(i - 49, i + 1);
      const sum50 = slice50.reduce((a, b) => a + b, 0);
      sma50Series.push(Number((sum50 / 50).toFixed(2)));
    } else {
      const slice50 = prices.slice(0, i + 1);
      const sum50 = slice50.reduce((a, b) => a + b, 0);
      sma50Series.push(Number((sum50 / (i + 1)).toFixed(2)));
    }
  }

  // Destroy previous Chart instance if active on canvas
  const existingChart = Chart.getChart(canvas);
  if (existingChart) {
    existingChart.destroy();
  }
  if (mainPriceChart) {
    try { mainPriceChart.destroy(); } catch (e) {}
    mainPriceChart = null;
  }

  const ctx = canvas.getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 360);
  if (isPositive) {
    gradient.addColorStop(0, 'rgba(22, 163, 74, 0.16)');
    gradient.addColorStop(1, 'rgba(22, 163, 74, 0.00)');
  } else {
    gradient.addColorStop(0, 'rgba(229, 57, 53, 0.16)');
    gradient.addColorStop(1, 'rgba(229, 57, 53, 0.00)');
  }

  mainPriceChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Close Price',
          data: prices,
          borderColor: lineColor,
          backgroundColor: gradient,
          borderWidth: 2,
          fill: true,
          tension: 0.15,
          pointRadius: validPoints.length > 60 ? 0 : 2,
          pointHoverRadius: 5
        },
        {
          label: 'MA 20 (SMA)',
          data: sma20Series,
          borderColor: '#d97706',
          borderWidth: 1.5,
          fill: false,
          tension: 0.15,
          pointRadius: 0,
          hidden: !showSMA20
        },
        {
          label: 'MA 50 (SMA)',
          data: sma50Series,
          borderColor: '#4f46e5',
          borderWidth: 1.5,
          fill: false,
          tension: 0.15,
          pointRadius: 0,
          hidden: !showSMA50
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'end',
          labels: {
            color: '#4b5563',
            boxWidth: 12,
            font: { size: 11, family: 'Inter' }
          }
        },
        tooltip: {
          backgroundColor: '#1f2937',
          titleColor: '#9ca3af',
          bodyColor: '#ffffff',
          borderColor: '#374151',
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: function(context) {
              return ` ${context.dataset.label}: ₹${Number(context.raw || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(0, 0, 0, 0.04)' },
          ticks: { color: '#64748b', maxTicksLimit: 7, font: { size: 10, family: 'Inter' } }
        },
        y: {
          grid: { color: 'rgba(0, 0, 0, 0.04)' },
          ticks: {
            color: '#64748b',
            font: { size: 10, family: 'Inter' },
            callback: function(val) { return '₹' + Number(val).toLocaleString('en-IN'); }
          }
        }
      }
    }
  });
}

// 5. Dedicated RSI Chart Visualization (0 to 100 Scale, Light Mode)
function renderRSIChart(series) {
  const canvas = document.getElementById('rsiChartCanvas');
  if (!canvas) return;

  const validSeries = series.filter(s => s.rsi !== null && s.rsi !== undefined);
  if (validSeries.length === 0) return;

  const labels = validSeries.map(s => s.date);
  const rsiValues = validSeries.map(s => s.rsi);

  if (rsiChart) {
    rsiChart.destroy();
  }

  const ctx = canvas.getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 180);
  gradient.addColorStop(0, 'rgba(37, 99, 235, 0.12)');
  gradient.addColorStop(1, 'rgba(37, 99, 235, 0.00)');

  rsiChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'RSI (14)',
          data: rsiValues,
          borderColor: '#2563eb',
          backgroundColor: gradient,
          borderWidth: 1.75,
          fill: true,
          tension: 0.15,
          pointRadius: 0,
          pointHoverRadius: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1f2937',
          borderColor: '#374151',
          borderWidth: 1,
          callbacks: {
            label: function(ctx) {
              return ` RSI (14): ${Number(ctx.raw || 0).toFixed(2)}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(0, 0, 0, 0.04)' },
          ticks: { color: '#64748b', maxTicksLimit: 5, font: { size: 9, family: 'Inter' } }
        },
        y: {
          min: 0,
          max: 100,
          ticks: {
            stepSize: 20,
            color: '#64748b',
            font: { size: 9, family: 'Inter' }
          },
          grid: {
            color: (ctx) => {
              if (ctx.tick.value === 70) return 'rgba(229, 57, 53, 0.4)'; // Overbought line
              if (ctx.tick.value === 30) return 'rgba(22, 163, 74, 0.4)'; // Oversold line
              if (ctx.tick.value === 50) return 'rgba(0, 0, 0, 0.08)';
              return 'rgba(0, 0, 0, 0.03)';
            }
          }
        }
      }
    }
  });
}

// 6. Dedicated MACD Chart Visualization (Line, Signal & Histogram, Light Mode)
function renderMACDChart(series) {
  const canvas = document.getElementById('macdChartCanvas');
  if (!canvas) return;

  const validSeries = series.filter(s => s.macd !== null && s.macd !== undefined);
  if (validSeries.length === 0) return;

  const labels = validSeries.map(s => s.date);
  const macdLine = validSeries.map(s => s.macd);
  const signalLine = validSeries.map(s => s.macd_signal);
  const histValues = validSeries.map(s => s.macd_hist);

  if (macdChart) {
    macdChart.destroy();
  }

  macdChart = new Chart(canvas, {
    data: {
      labels: labels,
      datasets: [
        {
          type: 'bar',
          label: 'Histogram',
          data: histValues,
          backgroundColor: (ctx) => {
            const val = ctx.raw || 0;
            return val >= 0 ? 'rgba(22, 163, 74, 0.75)' : 'rgba(229, 57, 53, 0.75)';
          },
          borderRadius: 2
        },
        {
          type: 'line',
          label: 'MACD (12,26)',
          data: macdLine,
          borderColor: '#2563eb',
          borderWidth: 1.5,
          fill: false,
          tension: 0.15,
          pointRadius: 0
        },
        {
          type: 'line',
          label: 'Signal (9)',
          data: signalLine,
          borderColor: '#d97706',
          borderWidth: 1.5,
          fill: false,
          tension: 0.15,
          pointRadius: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'end',
          labels: {
            color: '#4b5563',
            boxWidth: 10,
            font: { size: 9, family: 'Inter' }
          }
        },
        tooltip: {
          backgroundColor: '#1f2937',
          borderColor: '#374151',
          borderWidth: 1,
          callbacks: {
            label: function(ctx) {
              return ` ${ctx.dataset.label}: ${Number(ctx.raw || 0).toFixed(2)}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(0, 0, 0, 0.04)' },
          ticks: { color: '#64748b', maxTicksLimit: 5, font: { size: 9, family: 'Inter' } }
        },
        y: {
          grid: { color: 'rgba(0, 0, 0, 0.04)' },
          ticks: { color: '#64748b', font: { size: 9, family: 'Inter' } }
        }
      }
    }
  });
}

// 7. Setup Timeframe Buttons (1D, 1W, 1M, 6M, 1Y)
function setupTimeframeButtons() {
  const buttons = document.querySelectorAll('.tf-button');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const range = btn.getAttribute('data-range');
      loadPriceChart(range);
    });
  });
}

// 8. Watchlist State & Toggle
async function checkWatchlistState() {
  try {
    const res = await API.request(`/api/watchlist/check/${encodeURIComponent(currentSymbol)}`);
    if (res && res.data) {
      isSavedInWatchlist = res.data.is_saved;
      updateWatchlistButtonUI();
    }
  } catch (e) {
    console.warn(e);
  }
}

function updateWatchlistButtonUI() {
  const btn = document.getElementById('toggle-watchlist-btn');
  if (!btn) return;

  if (isSavedInWatchlist) {
    btn.className = 'btn-fintech btn-fintech-danger';
    btn.innerHTML = '<span>★</span> Added to Watchlist';
    btn.title = 'Click to remove from watchlist';
  } else {
    btn.className = 'btn-fintech btn-fintech-primary';
    btn.innerHTML = '<span>☆</span> Add to Watchlist';
    btn.title = 'Click to add to your watchlist';
  }
}

function setupWatchlistToggle() {
  const btn = document.getElementById('toggle-watchlist-btn');
  if (!btn) return;

  btn.addEventListener('click', async () => {
    try {
      btn.disabled = true;
      if (isSavedInWatchlist) {
        await API.request(`/api/watchlist/${encodeURIComponent(currentSymbol)}`, {
          method: 'DELETE'
        });
        isSavedInWatchlist = false;
        showToast(`Removed ${currentSymbol} from watchlist.`, 'info');
      } else {
        const compName = document.getElementById('stock-company-text').textContent;
        await API.request('/api/watchlist', {
          method: 'POST',
          body: JSON.stringify({
            symbol: currentSymbol,
            company_name: compName
          })
        });
        isSavedInWatchlist = true;
        showToast(`Added ${currentSymbol} to watchlist!`, 'success');
      }
      updateWatchlistButtonUI();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btn.disabled = false;
    }
  });
}

// 8b. Simulated Paper-Trading Holdings & Buy Modal Handlers
let currentStockHolding = null;

async function loadUserStockHolding() {
  const indicator = document.getElementById('user-holding-indicator');
  const qtyDisp = document.getElementById('holding-qty-disp');
  const avgDisp = document.getElementById('holding-avg-disp');
  const sellBtn = document.getElementById('paper-trade-sell-btn');
  if (!indicator) return;

  const ptOwnedDisp = document.getElementById('pt-sell-owned-qty');
  const ptAvgPriceSub = document.getElementById('pt-sell-avg-price-sub');
  const ptSellQtyInput = document.getElementById('pt-sell-qty-input');

  try {
    const res = await API.request(`/api/portfolio/holding/${encodeURIComponent(currentSymbol)}`);
    if (res && res.data && res.data.quantity > 0) {
      currentStockHolding = res.data;
      if (qtyDisp) qtyDisp.textContent = res.data.quantity;
      if (avgDisp) avgDisp.textContent = formatINR(res.data.average_buy_price);
      if (indicator) indicator.style.setProperty('display', 'flex', 'important');
      if (sellBtn) sellBtn.style.display = 'inline-flex';

      if (ptOwnedDisp) ptOwnedDisp.textContent = res.data.quantity;
      if (ptAvgPriceSub) ptAvgPriceSub.textContent = `(Avg: ${formatINR(res.data.average_buy_price)})`;
      if (ptSellQtyInput) ptSellQtyInput.max = res.data.quantity;
    } else {
      currentStockHolding = null;
      if (indicator) indicator.style.setProperty('display', 'none', 'important');
      if (sellBtn) sellBtn.style.display = 'none';

      if (ptOwnedDisp) ptOwnedDisp.textContent = '0';
      if (ptAvgPriceSub) ptAvgPriceSub.textContent = '(Avg: ₹0.00)';
      if (ptSellQtyInput) ptSellQtyInput.max = 1;
    }
  } catch (e) {
    currentStockHolding = null;
    if (indicator) indicator.style.setProperty('display', 'none', 'important');
    if (sellBtn) sellBtn.style.display = 'none';

    if (ptOwnedDisp) ptOwnedDisp.textContent = '0';
    if (ptAvgPriceSub) ptAvgPriceSub.textContent = '(Avg: ₹0.00)';
    if (ptSellQtyInput) ptSellQtyInput.max = 1;
  }

  if (typeof updatePtSellCalculations === 'function') {
    updatePtSellCalculations();
  }
}

function setupPaperTradeModal() {
  const buyBtn = document.getElementById('paper-trade-buy-btn');
  const buyModal = document.getElementById('paperTradeBuyModal');
  const qtyInput = document.getElementById('buy-quantity-input');
  const form = document.getElementById('paper-buy-form');
  const totalCostDisp = document.getElementById('modal-buy-total-cost');
  const remainBalDisp = document.getElementById('modal-buy-remaining-balance');
  const availCashDisp = document.getElementById('modal-buy-available-cash');
  const modalPriceDisp = document.getElementById('modal-buy-price');
  const modalSymbolDisp = document.getElementById('modal-buy-symbol');
  const modalCompanyDisp = document.getElementById('modal-buy-company');
  const modalExchangeDisp = document.getElementById('modal-buy-exchange');
  const errorAlert = document.getElementById('modal-buy-error-alert');
  const submitBtn = document.getElementById('modal-confirm-buy-btn');

  let userVirtualCash = 10000;

  function updateModalCalculations() {
    const price = (latestStockQuote && latestStockQuote.current_price) ? Number(latestStockQuote.current_price) : 0;
    const qty = parseInt(qtyInput ? qtyInput.value : 1, 10) || 0;
    const totalCost = qty * price;
    const remaining = userVirtualCash - totalCost;

    if (totalCostDisp) totalCostDisp.textContent = formatINR(totalCost);
    if (remainBalDisp) {
      remainBalDisp.textContent = formatINR(remaining);
      if (remaining < 0) {
        remainBalDisp.classList.add('text-danger');
        remainBalDisp.classList.remove('text-success');
      } else {
        remainBalDisp.classList.remove('text-danger');
        remainBalDisp.classList.add('text-success');
      }
    }

    if (submitBtn) {
      if (qty <= 0) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Enter Valid Quantity';
      } else if (remaining < 0) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Insufficient Virtual Funds';
      } else {
        submitBtn.disabled = false;
        submitBtn.textContent = `Confirm Buy (${qty} shares @ ${formatINR(price)})`;
      }
    }
  }

  if (buyBtn) {
    buyBtn.addEventListener('click', async () => {
      if (errorAlert) errorAlert.style.display = 'none';
      if (modalSymbolDisp) modalSymbolDisp.textContent = currentSymbol;
      if (modalCompanyDisp) modalCompanyDisp.textContent = (latestStockQuote && latestStockQuote.name) ? latestStockQuote.name : currentSymbol;
      if (modalExchangeDisp) modalExchangeDisp.textContent = (latestStockQuote && latestStockQuote.exchange) ? latestStockQuote.exchange : 'NSE';
      if (modalPriceDisp) modalPriceDisp.textContent = (latestStockQuote && latestStockQuote.current_price) ? formatINR(latestStockQuote.current_price) : 'Loading...';

      // Refresh latest virtual balance from backend
      try {
        const walletRes = await API.request('/api/user/wallet');
        if (walletRes && walletRes.data) {
          userVirtualCash = Number(walletRes.data.virtual_cash) || 0;
          if (availCashDisp) availCashDisp.textContent = formatINR(userVirtualCash);
        }
      } catch (e) {
        console.warn('Failed to refresh wallet:', e);
      }

      if (qtyInput) qtyInput.value = '1';
      updateModalCalculations();
    });
  }

  if (qtyInput) {
    qtyInput.addEventListener('input', updateModalCalculations);
    qtyInput.addEventListener('change', updateModalCalculations);
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const qty = parseInt(qtyInput ? qtyInput.value : 0, 10);
      if (!qty || qty <= 0) {
        if (errorAlert) {
          errorAlert.textContent = 'Please enter a positive whole share quantity.';
          errorAlert.style.display = 'block';
        }
        return;
      }

      try {
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Executing Simulated Order...';
        }
        if (errorAlert) errorAlert.style.display = 'none';

        const res = await API.request('/api/portfolio/buy', {
          method: 'POST',
          body: JSON.stringify({
            symbol: currentSymbol,
            quantity: qty
          })
        });

        if (!res || res.status === 'error') {
          throw new Error(res.message || 'Transaction failed.');
        }

        showToast(res.message || `Order executed: Bought ${qty} shares of ${currentSymbol}!`, 'success');

        // Update topbar balance display
        if (res.data && res.data.wallet) {
          const topbarBal = document.getElementById('topbar-virtual-balance');
          if (topbarBal) topbarBal.textContent = formatINR(res.data.wallet.virtual_cash);
        }

        // Refresh user holding on page
        await loadUserStockHolding();
        if (typeof updatePaperTradeSection === 'function') {
          updatePaperTradeSection();
        }

        // Close modal
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
          const bsModal = bootstrap.Modal.getInstance(buyModal) || new bootstrap.Modal(buyModal);
          bsModal.hide();
        } else {
          const closeBtn = buyModal ? buyModal.querySelector('.btn-close') : null;
          if (closeBtn) closeBtn.click();
        }

      } catch (err) {
        if (errorAlert) {
          errorAlert.textContent = err.message;
          errorAlert.style.display = 'block';
        }
        showToast(err.message, 'error');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Confirm Simulated Buy';
        }
      }
    });
  }
}

function setupPaperTradeSellModal() {
  const sellBtn = document.getElementById('paper-trade-sell-btn');
  const sellModal = document.getElementById('paperTradeSellModal');
  const qtyInput = document.getElementById('modal-sell-qty-input');
  const maxBtn = document.getElementById('modal-sell-max-btn');
  const form = document.getElementById('paper-sell-form');
  const proceedsDisp = document.getElementById('modal-sell-total-proceeds');
  const pnlDisp = document.getElementById('modal-sell-realized-pnl');
  const remainQtyDisp = document.getElementById('modal-sell-remaining-qty');
  const projCashDisp = document.getElementById('modal-sell-projected-cash');
  const modalSymbolDisp = document.getElementById('modal-sell-symbol');
  const modalPriceDisp = document.getElementById('modal-sell-current-price');
  const modalOwnedDisp = document.getElementById('modal-sell-owned-qty');
  const modalAvgDisp = document.getElementById('modal-sell-avg-price');
  const errorAlert = document.getElementById('modal-sell-error-alert');
  const submitBtn = document.getElementById('modal-confirm-sell-btn');

  let userVirtualCash = 10000;

  function updateSellCalculations() {
    if (!currentStockHolding) return;
    const price = (latestStockQuote && latestStockQuote.current_price) ? Number(latestStockQuote.current_price) : Number(currentStockHolding.average_buy_price);
    const owned = Number(currentStockHolding.quantity) || 0;
    const avg = Number(currentStockHolding.average_buy_price) || 0;
    const qty = parseInt(qtyInput ? qtyInput.value : 1, 10) || 0;

    const proceeds = Math.round(qty * price * 100) / 100;
    const costBasis = Math.round(qty * avg * 100) / 100;
    const realizedPnl = Math.round((proceeds - costBasis) * 100) / 100;
    const remainingQty = owned - qty;
    const projCash = Math.round((userVirtualCash + proceeds) * 100) / 100;

    if (proceedsDisp) proceedsDisp.textContent = formatINR(proceeds);
    if (remainQtyDisp) remainQtyDisp.textContent = remainingQty;
    if (projCashDisp) projCashDisp.textContent = formatINR(projCash);

    if (pnlDisp) {
      const isProfit = (realizedPnl >= 0);
      const sign = isProfit ? '+' : '';
      pnlDisp.textContent = `${sign}${formatINR(realizedPnl)}`;
      pnlDisp.className = `fw-bold num-mono ${isProfit ? 'text-success' : 'text-danger'}`;
    }

    if (submitBtn) {
      if (qty <= 0) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Enter Valid Quantity';
      } else if (qty > owned) {
        submitBtn.disabled = true;
        submitBtn.textContent = `Exceeds Owned (${owned} shares)`;
      } else {
        submitBtn.disabled = false;
        submitBtn.textContent = `Confirm Sell (${qty} shares @ ${formatINR(price)})`;
      }
    }
  }

  if (sellBtn) {
    sellBtn.addEventListener('click', async () => {
      if (errorAlert) errorAlert.style.display = 'none';
      if (!currentStockHolding) return;

      const price = (latestStockQuote && latestStockQuote.current_price) ? Number(latestStockQuote.current_price) : Number(currentStockHolding.average_buy_price);
      if (modalSymbolDisp) modalSymbolDisp.textContent = currentSymbol;
      if (modalPriceDisp) modalPriceDisp.textContent = formatINR(price);
      if (modalOwnedDisp) modalOwnedDisp.textContent = currentStockHolding.quantity;
      if (modalAvgDisp) modalAvgDisp.textContent = formatINR(currentStockHolding.average_buy_price);

      // Refresh latest virtual balance
      try {
        const walletRes = await API.request('/api/user/wallet');
        if (walletRes && walletRes.data) {
          userVirtualCash = Number(walletRes.data.virtual_cash) || 0;
        }
      } catch (e) {
        console.warn('Failed to refresh wallet:', e);
      }

      if (qtyInput) {
        qtyInput.max = currentStockHolding.quantity;
        qtyInput.value = '1';
      }
      updateSellCalculations();
    });
  }

  if (maxBtn) {
    maxBtn.addEventListener('click', () => {
      if (currentStockHolding && qtyInput) {
        qtyInput.value = currentStockHolding.quantity;
        updateSellCalculations();
      }
    });
  }

  if (qtyInput) {
    qtyInput.addEventListener('input', updateSellCalculations);
    qtyInput.addEventListener('change', updateSellCalculations);
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!currentStockHolding) return;

      const qty = parseInt(qtyInput ? qtyInput.value : 0, 10);
      if (!qty || qty <= 0 || qty > currentStockHolding.quantity) {
        if (errorAlert) {
          errorAlert.textContent = `Please enter a valid quantity between 1 and ${currentStockHolding.quantity}.`;
          errorAlert.style.display = 'block';
        }
        return;
      }

      try {
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Executing Simulated Order...';
        }
        if (errorAlert) errorAlert.style.display = 'none';

        const res = await API.request('/api/portfolio/sell', {
          method: 'POST',
          body: JSON.stringify({
            symbol: currentSymbol,
            quantity: qty
          })
        });

        if (!res || res.status === 'error') {
          throw new Error(res.message || 'Transaction failed.');
        }

        showToast(res.message || `Order executed: Sold ${qty} shares of ${currentSymbol}!`, 'success');

        // Update topbar balance display
        if (res.data && res.data.wallet) {
          const topbarBal = document.getElementById('topbar-virtual-balance');
          if (topbarBal) topbarBal.textContent = formatINR(res.data.wallet.virtual_cash);
        }

        // Refresh user holding on page
        await loadUserStockHolding();
        if (typeof updatePaperTradeSection === 'function') {
          updatePaperTradeSection();
        }

        // Close modal
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
          const bsModal = bootstrap.Modal.getInstance(sellModal) || new bootstrap.Modal(sellModal);
          bsModal.hide();
        } else {
          const closeBtn = sellModal ? sellModal.querySelector('.btn-close') : null;
          if (closeBtn) closeBtn.click();
        }

      } catch (err) {
        if (errorAlert) {
          errorAlert.textContent = err.message;
          errorAlert.style.display = 'block';
        }
        showToast(err.message, 'error');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Confirm Simulated Sell';
        }
      }
    });
  }
}

// =========================================================================
// 8c. In-Page Paper Trading (BUY / SELL) Engine
// =========================================================================

let inpageUserCash = 10000;

window.setPtBuyPreset = function(qty) {
  const input = document.getElementById('pt-buy-qty-input');
  if (input) {
    input.value = qty;
    updatePtBuyCalculations();
  }
};

function updatePtBuyCalculations() {
  const price = (latestStockQuote && latestStockQuote.current_price) ? Number(latestStockQuote.current_price) : 0;
  const qtyInput = document.getElementById('pt-buy-qty-input');
  const qty = parseInt(qtyInput ? qtyInput.value : 1, 10) || 0;
  const totalCost = Math.round(qty * price * 100) / 100;
  const remainingCash = Math.round((inpageUserCash - totalCost) * 100) / 100;

  const costDisp = document.getElementById('pt-buy-total-cost');
  const remainDisp = document.getElementById('pt-buy-remaining-cash');
  const submitBtn = document.getElementById('pt-buy-confirm-btn');

  if (costDisp) costDisp.textContent = formatINR(totalCost);
  if (remainDisp) {
    remainDisp.textContent = formatINR(remainingCash);
    if (remainingCash < 0) {
      remainDisp.className = 'fw-semibold num-mono text-danger';
    } else {
      remainDisp.className = 'fw-semibold num-mono text-success';
    }
  }

  if (submitBtn) {
    if (qty <= 0) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Enter Valid Quantity';
    } else if (remainingCash < 0) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Insufficient Virtual Cash';
    } else {
      submitBtn.disabled = false;
      submitBtn.textContent = `Confirm BUY (${qty} shares @ ${formatINR(price)})`;
    }
  }
}

function updatePtSellCalculations() {
  const price = (latestStockQuote && latestStockQuote.current_price) ? Number(latestStockQuote.current_price) : 0;
  const owned = currentStockHolding ? Number(currentStockHolding.quantity) || 0 : 0;
  const avgPrice = currentStockHolding ? Number(currentStockHolding.average_buy_price) || 0 : 0;
  const qtyInput = document.getElementById('pt-sell-qty-input');
  const qty = parseInt(qtyInput ? qtyInput.value : 1, 10) || 0;

  const totalValue = Math.round(qty * price * 100) / 100;
  const costBasis = Math.round(qty * avgPrice * 100) / 100;
  const realizedPnl = Math.round((totalValue - costBasis) * 100) / 100;
  const projCash = Math.round((inpageUserCash + totalValue) * 100) / 100;

  const valDisp = document.getElementById('pt-sell-total-value');
  const pnlDisp = document.getElementById('pt-sell-realized-pnl');
  const projCashDisp = document.getElementById('pt-sell-projected-cash');
  const submitBtn = document.getElementById('pt-sell-confirm-btn');

  if (valDisp) valDisp.textContent = formatINR(totalValue);
  if (projCashDisp) projCashDisp.textContent = formatINR(projCash);

  if (pnlDisp) {
    if (owned > 0 && qty > 0) {
      const isProfit = realizedPnl >= 0;
      const sign = isProfit ? '+' : '';
      pnlDisp.textContent = `${sign}${formatINR(realizedPnl)}`;
      pnlDisp.className = `fw-bold num-mono ${isProfit ? 'text-success' : 'text-danger'}`;
    } else {
      pnlDisp.textContent = '₹0.00';
      pnlDisp.className = 'fw-bold num-mono text-muted';
    }
  }

  if (submitBtn) {
    if (owned <= 0) {
      submitBtn.disabled = true;
      submitBtn.textContent = `No ${currentSymbol} Shares Owned`;
    } else if (qty <= 0) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Enter Valid Quantity';
    } else if (qty > owned) {
      submitBtn.disabled = true;
      submitBtn.textContent = `Exceeds Owned (${owned} shares)`;
    } else {
      submitBtn.disabled = false;
      submitBtn.textContent = `Confirm SELL (${qty} shares @ ${formatINR(price)})`;
    }
  }
}

async function updatePaperTradeSection() {
  const badge = document.getElementById('pt-selected-symbol-badge');
  if (badge) badge.textContent = currentSymbol;

  const price = (latestStockQuote && latestStockQuote.current_price) ? Number(latestStockQuote.current_price) : 0;
  const buyPriceDisp = document.getElementById('pt-buy-current-price');
  const sellPriceDisp = document.getElementById('pt-sell-current-price');

  if (buyPriceDisp) buyPriceDisp.textContent = formatINR(price);
  if (sellPriceDisp) sellPriceDisp.textContent = formatINR(price);

  // Fetch latest virtual cash balance
  try {
    const res = await API.request('/api/user/wallet');
    if (res && res.data) {
      inpageUserCash = Number(res.data.virtual_cash) || 0;
      const availCashDisp = document.getElementById('pt-buy-available-cash');
      if (availCashDisp) availCashDisp.textContent = formatINR(inpageUserCash);
      const topbarBal = document.getElementById('topbar-virtual-balance');
      if (topbarBal) topbarBal.textContent = formatINR(inpageUserCash);
    }
  } catch (e) {
    console.warn('Could not refresh virtual cash for paper trade section:', e);
  }

  // Update owned display in SELL tab
  const ownedQtyDisp = document.getElementById('pt-sell-owned-qty');
  const avgPriceSub = document.getElementById('pt-sell-avg-price-sub');
  const sellQtyInput = document.getElementById('pt-sell-qty-input');

  const owned = currentStockHolding ? Number(currentStockHolding.quantity) || 0 : 0;
  const avg = currentStockHolding ? Number(currentStockHolding.average_buy_price) || 0 : 0;

  if (ownedQtyDisp) ownedQtyDisp.textContent = owned;
  if (avgPriceSub) avgPriceSub.textContent = `(Avg: ${formatINR(avg)})`;
  if (sellQtyInput) {
    sellQtyInput.max = owned > 0 ? owned : 1;
    if (owned <= 0) sellQtyInput.value = '1';
  }

  // Recalculate preview numbers
  updatePtBuyCalculations();
  updatePtSellCalculations();
}

function setupInPagePaperTrade() {
  const buyForm = document.getElementById('pt-buy-form');
  const sellForm = document.getElementById('pt-sell-form');
  const buyQtyInput = document.getElementById('pt-buy-qty-input');
  const sellQtyInput = document.getElementById('pt-sell-qty-input');
  const sellMaxBtn = document.getElementById('pt-sell-max-btn');

  // Input listeners
  if (buyQtyInput) {
    buyQtyInput.addEventListener('input', updatePtBuyCalculations);
    buyQtyInput.addEventListener('change', updatePtBuyCalculations);
  }

  if (sellQtyInput) {
    sellQtyInput.addEventListener('input', updatePtSellCalculations);
    sellQtyInput.addEventListener('change', updatePtSellCalculations);
  }

  if (sellMaxBtn) {
    sellMaxBtn.addEventListener('click', () => {
      const owned = currentStockHolding ? Number(currentStockHolding.quantity) || 0 : 0;
      if (owned > 0 && sellQtyInput) {
        sellQtyInput.value = owned;
        updatePtSellCalculations();
      }
    });
  }

  // Handle Tab Switch Recalculations
  const buyTab = document.getElementById('pt-tab-buy');
  const sellTab = document.getElementById('pt-tab-sell');
  if (buyTab) {
    buyTab.addEventListener('shown.bs.tab', () => updatePtBuyCalculations());
  }
  if (sellTab) {
    sellTab.addEventListener('shown.bs.tab', () => updatePtSellCalculations());
  }

  // BUY Form Submit
  if (buyForm) {
    buyForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const qty = parseInt(buyQtyInput ? buyQtyInput.value : 0, 10);
      const errorAlert = document.getElementById('pt-buy-error-alert');
      const successAlert = document.getElementById('pt-buy-success-alert');
      const submitBtn = document.getElementById('pt-buy-confirm-btn');
      const spinner = document.getElementById('pt-buy-spinner');

      if (!qty || qty <= 0) {
        if (errorAlert) {
          errorAlert.textContent = 'Please enter a positive whole share quantity.';
          errorAlert.style.display = 'block';
        }
        if (successAlert) successAlert.style.display = 'none';
        return;
      }

      try {
        if (submitBtn) submitBtn.disabled = true;
        if (spinner) spinner.classList.remove('d-none');
        if (errorAlert) errorAlert.style.display = 'none';
        if (successAlert) successAlert.style.display = 'none';

        const res = await API.request('/api/portfolio/buy', {
          method: 'POST',
          body: JSON.stringify({
            symbol: currentSymbol,
            quantity: qty
          })
        });

        if (!res || res.status === 'error') {
          throw new Error(res.message || 'Simulated BUY transaction failed.');
        }

        const successMsg = res.message || `Successfully bought ${qty} share(s) of ${currentSymbol}!`;
        if (successAlert) {
          successAlert.textContent = `✓ ${successMsg}`;
          successAlert.style.display = 'block';
        }
        showToast(successMsg, 'success');

        // Update virtual cash & holdings
        if (res.data && res.data.wallet) {
          inpageUserCash = Number(res.data.wallet.virtual_cash) || 0;
          const availCashDisp = document.getElementById('pt-buy-available-cash');
          if (availCashDisp) availCashDisp.textContent = formatINR(inpageUserCash);
          const topbarBal = document.getElementById('topbar-virtual-balance');
          if (topbarBal) topbarBal.textContent = formatINR(inpageUserCash);
        }

        // Re-load user holding and update paper trade displays
        await loadUserStockHolding();
        updatePaperTradeSection();

      } catch (err) {
        if (errorAlert) {
          errorAlert.textContent = `⚠️ ${err.message}`;
          errorAlert.style.display = 'block';
        }
        if (successAlert) successAlert.style.display = 'none';
        showToast(err.message, 'error');
      } finally {
        if (submitBtn) submitBtn.disabled = false;
        if (spinner) spinner.classList.add('d-none');
        updatePtBuyCalculations();
      }
    });
  }

  // SELL Form Submit
  if (sellForm) {
    sellForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const qty = parseInt(sellQtyInput ? sellQtyInput.value : 0, 10);
      const owned = currentStockHolding ? Number(currentStockHolding.quantity) || 0 : 0;
      const errorAlert = document.getElementById('pt-sell-error-alert');
      const successAlert = document.getElementById('pt-sell-success-alert');
      const submitBtn = document.getElementById('pt-sell-confirm-btn');
      const spinner = document.getElementById('pt-sell-spinner');

      if (!owned || owned <= 0) {
        if (errorAlert) {
          errorAlert.textContent = `You do not own any shares of ${currentSymbol} to sell.`;
          errorAlert.style.display = 'block';
        }
        if (successAlert) successAlert.style.display = 'none';
        return;
      }

      if (!qty || qty <= 0 || qty > owned) {
        if (errorAlert) {
          errorAlert.textContent = `Please enter a valid quantity between 1 and ${owned}.`;
          errorAlert.style.display = 'block';
        }
        if (successAlert) successAlert.style.display = 'none';
        return;
      }

      try {
        if (submitBtn) submitBtn.disabled = true;
        if (spinner) spinner.classList.remove('d-none');
        if (errorAlert) errorAlert.style.display = 'none';
        if (successAlert) successAlert.style.display = 'none';

        const res = await API.request('/api/portfolio/sell', {
          method: 'POST',
          body: JSON.stringify({
            symbol: currentSymbol,
            quantity: qty
          })
        });

        if (!res || res.status === 'error') {
          throw new Error(res.message || 'Simulated SELL transaction failed.');
        }

        const successMsg = res.message || `Successfully sold ${qty} share(s) of ${currentSymbol}!`;
        if (successAlert) {
          successAlert.textContent = `✓ ${successMsg}`;
          successAlert.style.display = 'block';
        }
        showToast(successMsg, 'success');

        // Update virtual cash & holdings
        if (res.data && res.data.wallet) {
          inpageUserCash = Number(res.data.wallet.virtual_cash) || 0;
          const availCashDisp = document.getElementById('pt-buy-available-cash');
          if (availCashDisp) availCashDisp.textContent = formatINR(inpageUserCash);
          const topbarBal = document.getElementById('topbar-virtual-balance');
          if (topbarBal) topbarBal.textContent = formatINR(inpageUserCash);
        }

        // Re-load user holding and update paper trade displays
        await loadUserStockHolding();
        updatePaperTradeSection();

      } catch (err) {
        if (errorAlert) {
          errorAlert.textContent = `⚠️ ${err.message}`;
          errorAlert.style.display = 'block';
        }
        if (successAlert) successAlert.style.display = 'none';
        showToast(err.message, 'error');
      } finally {
        if (submitBtn) submitBtn.disabled = false;
        if (spinner) spinner.classList.add('d-none');
        updatePtSellCalculations();
      }
    });
  }
}

// =========================================================================
// 6. Fetch & Render Machine Learning Price Prediction
// =========================================================================
async function loadMLPrediction() {
  const loadingElem = document.getElementById('ml-prediction-loading');
  const errorElem = document.getElementById('ml-prediction-error');
  const errorMsgElem = document.getElementById('ml-error-message');
  const contentElem = document.getElementById('ml-prediction-content');
  const badgeElem = document.getElementById('ml-best-model-badge');

  if (!loadingElem || !contentElem) return;

  // Show loading state, hide error and previous content
  loadingElem.style.display = 'block';
  if (errorElem) errorElem.style.display = 'none';
  contentElem.style.display = 'none';
  if (badgeElem) badgeElem.textContent = 'Calculating...';

  try {
    const res = await API.request(`/api/ml/predict/${encodeURIComponent(currentSymbol)}`);
    if (res && res.status === 'success' && res.data) {
      const d = res.data;

      // 1. Current Price
      const curPriceElem = document.getElementById('ml-current-price');
      if (curPriceElem) curPriceElem.textContent = formatINR(d.current_price);

      // 2. Predicted Next-Day Price
      const predPriceElem = document.getElementById('ml-predicted-price');
      if (predPriceElem) predPriceElem.textContent = formatINR(d.predicted_price);

      // 3. Expected Change & Expected Change %
      const changeVal = Number(d.prediction_change) || 0;
      const changePctVal = Number(d.prediction_change_percentage) || 0;
      const isPositive = changeVal >= 0;

      const changeElem = document.getElementById('ml-expected-change');
      if (changeElem) {
        const prefix = changeVal > 0 ? '+' : '';
        changeElem.textContent = `${prefix}${formatINR(changeVal)}`;
        changeElem.style.color = isPositive ? 'var(--color-up-dark)' : 'var(--color-down)';
      }

      const changePctElem = document.getElementById('ml-expected-change-pct');
      if (changePctElem) {
        changePctElem.textContent = `${formatPercent(changePctVal)} expected`;
        changePctElem.style.color = isPositive ? 'var(--color-up-dark)' : 'var(--color-down)';
      }

      // Direction Pill
      const pillElem = document.getElementById('ml-direction-pill');
      if (pillElem) {
        pillElem.textContent = isPositive ? '▲ BULLISH' : '▼ BEARISH';
        pillElem.className = `delta-pill num-mono ${isPositive ? 'positive' : 'negative'}`;
      }

      // 4. Best Model
      const bestModelName = d.selected_model || 'Linear Regression';
      const bestModelElem = document.getElementById('ml-best-model-name');
      if (bestModelElem) bestModelElem.textContent = bestModelName;

      if (badgeElem) {
        badgeElem.textContent = `Best: ${bestModelName}`;
      }

      // 5. Evaluation Metrics (MAE, RMSE, R²)
      const metrics = (bestModelName.includes('Random Forest'))
        ? d.random_forest_metrics
        : d.linear_regression_metrics;

      const maeElem = document.getElementById('ml-metric-mae');
      if (maeElem) {
        maeElem.textContent = (metrics && metrics.mae !== undefined && metrics.mae !== null) ? Number(metrics.mae).toFixed(2) : '--';
      }

      const rmseElem = document.getElementById('ml-metric-rmse');
      if (rmseElem) {
        rmseElem.textContent = (metrics && metrics.rmse !== undefined && metrics.rmse !== null) ? Number(metrics.rmse).toFixed(2) : '--';
      }

      const r2Elem = document.getElementById('ml-metric-r2');
      if (r2Elem) {
        const r2Val = (metrics && metrics.r2 !== undefined && metrics.r2 !== null) ? Number(metrics.r2) : null;
        if (r2Val !== null) {
          r2Elem.textContent = r2Val.toFixed(4);
          r2Elem.style.color = r2Val >= 0.7 ? 'var(--color-up-dark)' : (r2Val >= 0.4 ? 'var(--color-neutral)' : 'var(--text-secondary)');
        } else {
          r2Elem.textContent = '--';
          r2Elem.style.color = 'var(--text-secondary)';
        }
      }

      // Timestamp
      const timeElem = document.getElementById('ml-prediction-timestamp');
      if (timeElem && d.timestamp) {
        timeElem.textContent = `Forecast: ${d.timestamp}`;
      }

      // Render content
      loadingElem.style.display = 'none';
      contentElem.style.display = 'block';
    } else {
      throw new Error((res && res.message) || 'Prediction calculation returned no data.');
    }
  } catch (err) {
    loadingElem.style.display = 'none';
    if (badgeElem) badgeElem.textContent = 'Error';
    if (errorElem) {
      if (errorMsgElem) {
        errorMsgElem.textContent = err.message || 'Unable to compute ML prediction for this stock.';
      }
      errorElem.style.display = 'block';
    }
  }
}

// =========================================================================
// 7. Fetch & Render AI Recommendation (BUY / HOLD / SELL)
// =========================================================================
async function loadAIRecommendation() {
  const loadingElem = document.getElementById('ai-rec-loading');
  const errorElem = document.getElementById('ai-rec-error');
  const errorMsgElem = document.getElementById('ai-rec-error-message');
  const contentElem = document.getElementById('ai-rec-content');
  const badgeElem = document.getElementById('ai-rec-badge');
  const verdictBox = document.getElementById('ai-rec-verdict-box');
  const verdictText = document.getElementById('ai-rec-verdict-text');
  const scorePill = document.getElementById('ai-rec-score-pill');
  const normalizedElem = document.getElementById('ai-rec-normalized-score');

  if (!loadingElem || !contentElem) return;

  // Show loading state, hide error and previous content
  loadingElem.style.display = 'block';
  if (errorElem) errorElem.style.display = 'none';
  contentElem.style.display = 'none';
  if (badgeElem) {
    badgeElem.textContent = 'Calculating...';
    badgeElem.style.color = '#2563eb';
    badgeElem.style.borderColor = 'rgba(37, 99, 235, 0.25)';
    badgeElem.style.backgroundColor = 'rgba(37, 99, 235, 0.06)';
  }

  try {
    const res = await API.request(`/api/recommendation/${encodeURIComponent(currentSymbol)}`);
    if (res && res.status === 'success' && res.data) {
      const d = res.data;

      // 1. Recommendation Verdict (BUY / HOLD / SELL)
      const rec = (d.recommendation || 'HOLD').toUpperCase();
      if (verdictText) verdictText.textContent = rec;

      if (badgeElem) {
        badgeElem.textContent = rec;
      }

      if (rec === 'BUY') {
        if (verdictText) verdictText.style.color = 'var(--color-up-dark)';
        if (badgeElem) {
          badgeElem.style.color = 'var(--color-up-dark)';
          badgeElem.style.borderColor = 'var(--color-up-border)';
          badgeElem.style.backgroundColor = 'var(--color-up-bg)';
        }
        if (verdictBox) {
          verdictBox.style.borderColor = 'rgba(22, 163, 74, 0.3)';
          verdictBox.style.backgroundColor = 'rgba(22, 163, 74, 0.04)';
        }
      } else if (rec === 'SELL') {
        if (verdictText) verdictText.style.color = 'var(--color-down)';
        if (badgeElem) {
          badgeElem.style.color = 'var(--color-down)';
          badgeElem.style.borderColor = 'var(--color-down-border)';
          badgeElem.style.backgroundColor = 'var(--color-down-bg)';
        }
        if (verdictBox) {
          verdictBox.style.borderColor = 'rgba(229, 57, 53, 0.3)';
          verdictBox.style.backgroundColor = 'rgba(229, 57, 53, 0.04)';
        }
      } else {
        // HOLD
        if (verdictText) verdictText.style.color = 'var(--color-neutral)';
        if (badgeElem) {
          badgeElem.style.color = 'var(--color-neutral)';
          badgeElem.style.borderColor = 'rgba(217, 119, 6, 0.25)';
          badgeElem.style.backgroundColor = 'rgba(217, 119, 6, 0.08)';
        }
        if (verdictBox) {
          verdictBox.style.borderColor = 'var(--border-default)';
          verdictBox.style.backgroundColor = '#f8fafc';
        }
      }

      // 2. Signal Score
      const score = Number(d.signal_score) || 0;
      if (scorePill) {
        const scorePrefix = score > 0 ? '+' : '';
        scorePill.textContent = `Score: ${scorePrefix}${score}`;
        scorePill.className = `delta-pill num-mono ${score > 15 ? 'positive' : (score < -15 ? 'negative' : 'neutral')}`;
      }

      if (normalizedElem) {
        normalizedElem.textContent = d.normalized_score !== undefined ? `${d.normalized_score} / 100` : '--';
      }

      // 3. Current Price
      const curElem = document.getElementById('ai-rec-current-price');
      if (curElem) curElem.textContent = (d.current_price !== null && d.current_price !== undefined) ? formatINR(d.current_price) : '--';

      // 4. ML Predicted Price
      const predElem = document.getElementById('ai-rec-predicted-price');
      if (predElem) {
        if (d.predicted_price !== null && d.predicted_price !== undefined) {
          predElem.textContent = formatINR(d.predicted_price);
        } else {
          predElem.textContent = '--';
        }
      }

      // 5. RSI (14)
      const rsiElem = document.getElementById('ai-rec-rsi');
      if (rsiElem) {
        if (d.rsi !== null && d.rsi !== undefined) {
          const rsiVal = Number(d.rsi);
          rsiElem.textContent = rsiVal.toFixed(2);
          if (rsiVal <= 30) rsiElem.style.color = 'var(--color-up-dark)';
          else if (rsiVal >= 70) rsiElem.style.color = 'var(--color-down)';
          else rsiElem.style.color = 'var(--text-white)';
        } else {
          rsiElem.textContent = '--';
        }
      }

      // 6. MACD
      const macdElem = document.getElementById('ai-rec-macd');
      if (macdElem) {
        if (d.macd !== null && d.macd !== undefined) {
          const macdVal = Number(d.macd);
          macdElem.textContent = macdVal.toFixed(2);
          macdElem.style.color = macdVal >= 0 ? 'var(--color-up-dark)' : 'var(--color-down)';
        } else {
          macdElem.textContent = '--';
        }
      }

      // 7. MA 20 & MA 50
      const ma20Elem = document.getElementById('ai-rec-ma20');
      if (ma20Elem) {
        ma20Elem.textContent = (d.ma20 !== null && d.ma20 !== undefined) ? formatINR(d.ma20) : '--';
      }

      const ma50Elem = document.getElementById('ai-rec-ma50');
      if (ma50Elem) {
        ma50Elem.textContent = (d.ma50 !== null && d.ma50 !== undefined) ? formatINR(d.ma50) : '--';
      }

      // 8. Natural Language Explanation
      const expElem = document.getElementById('ai-rec-explanation');
      if (expElem) {
        expElem.textContent = d.explanation || 'No explanation available.';
      }

      // Show content
      loadingElem.style.display = 'none';
      contentElem.style.display = 'block';
    } else {
      throw new Error((res && res.message) || 'Recommendation data could not be computed.');
    }
  } catch (err) {
    loadingElem.style.display = 'none';
    if (badgeElem) badgeElem.textContent = 'Error';
    if (errorElem) {
      if (errorMsgElem) {
        errorMsgElem.textContent = err.message || 'Unable to compute AI recommendation for this security.';
      }
      errorElem.style.display = 'block';
    }
  }
}
