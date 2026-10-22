/**
 * StockSense AI - Dedicated User Portfolio & Paper Trading Management Logic
 */

let userHoldings = [];
let userPortfolioSummary = null;
let currentSellingHolding = null;

document.addEventListener('DOMContentLoaded', () => {
  initPortfolioPage();
});

async function initPortfolioPage() {
  // Enforce client authentication guard
  const token = API.getToken();
  if (!token) {
    window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
    return;
  }

  await Promise.all([
    loadPortfolioSummary(),
    loadTransactions()
  ]);

  setupHoldingsFilter();
  setupSellModalEvents();

  const refreshBtn = document.getElementById('refresh-holdings-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.disabled = true;
      refreshBtn.innerHTML = '⏳ Refreshing...';
      await Promise.all([loadPortfolioSummary(), loadTransactions()]);
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = '🔄 Refresh';
      showToast('Portfolio real-time valuation refreshed.', 'info');
    });
  }
}

/**
 * Loads the complete authoritative portfolio summary and holdings from backend
 */
async function loadPortfolioSummary() {
  const tableBody = document.getElementById('holdings-table-body');
  const emptyState = document.getElementById('holdings-empty-state');
  const tableContainer = document.getElementById('holdings-table-container');
  const countBadge = document.getElementById('port-holdings-count-badge');

  try {
    const res = await API.request('/api/portfolio/summary');
    if (!res || !res.data) return;

    userPortfolioSummary = res.data;
    userHoldings = userPortfolioSummary.holdings || [];

    // 1. Render all 6 portfolio-level summary KPI cards
    renderPortfolioKPIs(userPortfolioSummary);

    // 2. Render Holdings Table or Empty State
    if (countBadge) {
      countBadge.textContent = `${userHoldings.length} Stock${userHoldings.length === 1 ? '' : 's'}`;
    }

    if (userHoldings.length === 0) {
      if (tableBody) tableBody.innerHTML = '';
      if (tableContainer) tableContainer.style.display = 'none';
      if (emptyState) emptyState.style.display = 'block';
      return;
    }

    if (emptyState) emptyState.style.display = 'none';
    if (tableContainer) tableContainer.style.display = 'block';

    renderHoldingsTable(userHoldings);

  } catch (err) {
    console.error('Error loading portfolio summary:', err);
    if (tableBody) {
      tableBody.innerHTML = `<tr><td colspan="10" class="text-center py-4 text-danger">Failed to load open positions. Please log in or refresh.</td></tr>`;
    }
  }
}

/**
 * Renders all 6 core portfolio-level KPI cards with exact calculations
 * 1. Virtual Cash
 * 2. Total Investment
 * 3. Current Portfolio Value
 * 4. Total Portfolio Value
 * 5. Total Profit/Loss
 * 6. Total Profit/Loss %
 */
function renderPortfolioKPIs(summary) {
  // 1. Virtual Cash
  const cashDisp = document.getElementById('port-virtual-cash');
  if (cashDisp) {
    cashDisp.textContent = `₹${summary.virtual_cash.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  const topbarBal = document.getElementById('topbar-virtual-balance');
  if (topbarBal) {
    topbarBal.textContent = `₹${summary.virtual_cash.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  // 2. Total Investment
  const investDisp = document.getElementById('port-total-investment');
  if (investDisp) {
    investDisp.textContent = `₹${summary.total_investment.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  // 3. Current Portfolio Value
  const currValDisp = document.getElementById('port-current-portfolio-value');
  if (currValDisp) {
    currValDisp.textContent = `₹${summary.current_portfolio_value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  // 4. Total Portfolio Value (Virtual Cash + Current Portfolio Value)
  const totalValDisp = document.getElementById('port-total-portfolio-value');
  if (totalValDisp) {
    totalValDisp.textContent = `₹${summary.total_portfolio_value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  // 5. Total Profit/Loss (Current Portfolio Value - Total Investment)
  const pnlDisp = document.getElementById('port-total-pnl');
  if (pnlDisp) {
    const isProfit = summary.total_pnl >= 0;
    const sign = isProfit ? '+' : '';
    pnlDisp.textContent = `${sign}₹${summary.total_pnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    pnlDisp.className = `fs-5 fw-bold num-mono mt-1 ${isProfit ? 'text-success' : 'text-danger'}`;
  }

  // 6. Total Profit/Loss %
  const pnlPctDisp = document.getElementById('port-total-pnl-pct');
  if (pnlPctDisp) {
    const isProfit = summary.total_pnl_percent >= 0;
    const sign = isProfit ? '+' : '';
    pnlPctDisp.textContent = `${sign}${summary.total_pnl_percent.toFixed(2)}%`;
    pnlPctDisp.className = `fs-5 fw-bold num-mono mt-1 ${isProfit ? 'text-success' : 'text-danger'}`;
  }
}

/**
 * Renders the holdings table containing all 9 requested columns:
 * 1. Stock Symbol
 * 2. Company Name
 * 3. Quantity
 * 4. Average Buy Price
 * 5. Current Price
 * 6. Invested Amount
 * 7. Current Value
 * 8. Profit/Loss
 * 9. Profit/Loss %
 * plus Actions
 */
function renderHoldingsTable(holdings) {
  const tableBody = document.getElementById('holdings-table-body');
  if (!tableBody) return;

  tableBody.innerHTML = '';

  holdings.forEach(item => {
    const qty = parseInt(item.quantity, 10) || 0;
    const avgPrice = parseFloat(item.average_buy_price) || 0;
    const currentPrice = parseFloat(item.current_price) || avgPrice;
    const investedAmount = parseFloat(item.invested_amount) || (qty * avgPrice);
    const currentValue = parseFloat(item.current_value) || (qty * currentPrice);
    const pnl = parseFloat(item.pnl) || (currentValue - investedAmount);
    const pnlPct = parseFloat(item.pnl_percent) || (investedAmount > 0 ? (pnl / investedAmount) * 100 : 0);

    const isProfit = (pnl >= 0);
    const pnlSign = isProfit ? '+' : '';
    const pnlClass = isProfit ? 'text-success' : 'text-danger';
    const pnlBadgeClass = isProfit ? 'bg-success-subtle text-success border border-success-subtle' : 'bg-danger-subtle text-danger border border-danger-subtle';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>
        <a href="/analysis/${encodeURIComponent(item.symbol)}" class="fw-bold num-mono text-decoration-none" style="color: #111827; font-size: 0.9rem;">
          ${item.symbol}
        </a>
      </td>
      <td>
        <span class="text-secondary" style="font-size:0.8rem;">${item.company_name || item.symbol}</span>
      </td>
      <td>
        <strong class="num-mono text-dark">${qty.toLocaleString('en-IN')}</strong>
      </td>
      <td>
        <span class="num-mono">₹${avgPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
      </td>
      <td>
        <strong class="num-mono text-dark">₹${currentPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
      </td>
      <td>
        <span class="num-mono text-secondary">₹${investedAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
      </td>
      <td>
        <strong class="num-mono text-dark">₹${currentValue.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
      </td>
      <td>
        <span class="num-mono fw-bold ${pnlClass}">
          ${pnlSign}₹${pnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      </td>
      <td>
        <span class="badge ${pnlBadgeClass} num-mono px-2 py-1" style="font-size: 0.775rem;">
          ${pnlSign}${pnlPct.toFixed(2)}%
        </span>
      </td>
      <td class="text-end">
        <div class="d-inline-flex gap-1">
          <button class="btn-fintech btn-open-sell-modal" 
                  data-symbol="${item.symbol}"
                  data-company="${item.company_name || item.symbol}"
                  data-qty="${qty}"
                  data-avg="${avgPrice}"
                  data-price="${currentPrice}"
                  style="background-color: #dc2626; color: #ffffff; border: 1px solid #b91c1c; padding: 4px 10px; font-size: 0.75rem; font-weight: 600;">
            📉 SELL
          </button>
          <a href="/analysis/${encodeURIComponent(item.symbol)}" class="btn-fintech btn-fintech-ghost" style="padding: 4px 10px; font-size: 0.75rem;">
            Buy More
          </a>
        </div>
      </td>
    `;
    tableBody.appendChild(tr);
  });

  // Attach sell button click handlers
  document.querySelectorAll('.btn-open-sell-modal').forEach(btn => {
    btn.addEventListener('click', () => {
      const holdingData = {
        symbol: btn.dataset.symbol,
        company_name: btn.dataset.company,
        quantity: parseInt(btn.dataset.qty, 10),
        average_buy_price: parseFloat(btn.dataset.avg),
        current_price: parseFloat(btn.dataset.price)
      };
      openSellModal(holdingData);
    });
  });
}

/**
 * Filter positions in real-time
 */
function setupHoldingsFilter() {
  const input = document.getElementById('holdings-search-input');
  if (!input) return;

  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    if (!q) {
      renderHoldingsTable(userHoldings);
      return;
    }
    const filtered = userHoldings.filter(h =>
      (h.symbol && h.symbol.toLowerCase().includes(q)) ||
      (h.company_name && h.company_name.toLowerCase().includes(q))
    );
    renderHoldingsTable(filtered);
  });
}

let userTransactions = [];
let currentTxFilter = 'ALL';

/**
 * Loads simulated order transaction history from the database
 */
async function loadTransactions() {
  const tableBody = document.getElementById('transactions-table-body');
  const countBadge = document.getElementById('port-transactions-count-badge');
  if (!tableBody) return;

  try {
    const res = await API.request('/api/portfolio/transactions');
    if (!res || !res.data) return;

    userTransactions = res.data;
    if (countBadge) {
      countBadge.textContent = `${userTransactions.length} Trade${userTransactions.length === 1 ? '' : 's'}`;
    }

    renderTransactionsTable(userTransactions);
    setupTransactionFilterButtons();

  } catch (err) {
    console.error('Error loading transactions:', err);
    if (tableBody) {
      tableBody.innerHTML = `<tr><td colspan="8" class="text-center py-3 text-muted">Unable to load trade history.</td></tr>`;
    }
  }
}

/**
 * Renders transactions table with exact requested columns:
 * 1. Date/Time
 * 2. Stock Symbol
 * 3. BUY / SELL
 * 4. Quantity
 * 5. Execution Price
 * 6. Total Amount
 * 7. Realized P&L
 * 8. Status
 */
function renderTransactionsTable(txs) {
  const tableBody = document.getElementById('transactions-table-body');
  const emptyState = document.getElementById('transactions-empty-state');
  if (!tableBody) return;

  const filtered = currentTxFilter === 'ALL'
    ? txs
    : txs.filter(t => (t.transaction_type || '').toUpperCase() === currentTxFilter);

  if (filtered.length === 0) {
    tableBody.innerHTML = '';
    if (emptyState) emptyState.style.display = 'block';
    return;
  }

  if (emptyState) emptyState.style.display = 'none';
  tableBody.innerHTML = '';

  filtered.forEach(t => {
    const isBuy = (t.transaction_type === 'BUY');
    const typeBadge = isBuy
      ? '<span class="badge bg-success-subtle text-success border border-success-subtle num-mono px-2 py-1">BUY</span>'
      : '<span class="badge bg-danger-subtle text-danger border border-danger-subtle num-mono px-2 py-1">SELL</span>';

    const dateStr = t.created_at ? new Date(t.created_at).toLocaleString('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'short'
    }) : '--';

    let pnlDisplay = '—';
    if (!isBuy && t.realized_pnl !== undefined && t.realized_pnl !== null) {
      const pnlVal = parseFloat(t.realized_pnl);
      const pnlSign = pnlVal >= 0 ? '+' : '';
      const pnlClass = pnlVal >= 0 ? 'text-success fw-bold' : 'text-danger fw-bold';
      pnlDisplay = `<span class="${pnlClass} num-mono">${pnlSign}₹${pnlVal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>`;
    }

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="text-secondary num-mono" style="font-size:0.775rem;">${dateStr}</td>
      <td>
        <a href="/analysis/${encodeURIComponent(t.symbol)}" class="fw-bold num-mono text-decoration-none" style="color: #111827;">${t.symbol}</a>
        <div class="text-muted" style="font-size:0.72rem;">${t.company_name || t.symbol}</div>
      </td>
      <td>${typeBadge}</td>
      <td><strong class="num-mono text-dark">${t.quantity.toLocaleString('en-IN')}</strong></td>
      <td><span class="num-mono">₹${parseFloat(t.price).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></td>
      <td><strong class="num-mono text-dark">₹${parseFloat(t.total_amount).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong></td>
      <td>${pnlDisplay}</td>
      <td><span class="badge bg-secondary-subtle text-secondary" style="font-size: 0.7rem;">${t.status}</span></td>
    `;
    tableBody.appendChild(tr);
  });
}

function setupTransactionFilterButtons() {
  const btnAll = document.getElementById('tx-filter-all');
  const btnBuy = document.getElementById('tx-filter-buy');
  const btnSell = document.getElementById('tx-filter-sell');
  if (!btnAll || !btnBuy || !btnSell) return;

  const setActive = (activeBtn, filter) => {
    [btnAll, btnBuy, btnSell].forEach(b => b.classList.remove('active'));
    activeBtn.classList.add('active');
    currentTxFilter = filter;
    renderTransactionsTable(userTransactions);
  };

  btnAll.onclick = () => setActive(btnAll, 'ALL');
  btnBuy.onclick = () => setActive(btnBuy, 'BUY');
  btnSell.onclick = () => setActive(btnSell, 'SELL');
}

/**
 * Opens and configures the Sell Modal for a specific holding
 */
function openSellModal(holding) {
  currentSellingHolding = holding;

  const modalEl = document.getElementById('sellStockModal');
  if (!modalEl) return;

  document.getElementById('sell-modal-symbol').textContent = holding.symbol;
  document.getElementById('sell-modal-company').textContent = holding.company_name;
  document.getElementById('sell-modal-owned-qty').textContent = holding.quantity;
  document.getElementById('sell-modal-current-price').textContent = `₹${holding.current_price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  document.getElementById('sell-modal-avg-price').textContent = `₹${holding.average_buy_price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const qtyInput = document.getElementById('sell-quantity-input');
  qtyInput.max = holding.quantity;
  qtyInput.value = 1;

  const errorBox = document.getElementById('sell-modal-error');
  if (errorBox) errorBox.style.display = 'none';

  updateSellModalCalculations();

  const modal = new bootstrap.Modal(modalEl);
  modal.show();
}

/**
 * Computes live sell values and estimated realized P&L as the user adjusts quantity
 */
function updateSellModalCalculations() {
  if (!currentSellingHolding) return;

  const qtyInput = document.getElementById('sell-quantity-input');
  const confirmBtn = document.getElementById('confirm-sell-btn');
  const errorBox = document.getElementById('sell-modal-error');

  const rawQty = qtyInput.value;
  const qty = parseInt(rawQty, 10);
  const owned = currentSellingHolding.quantity;
  const currentPrice = currentSellingHolding.current_price;
  const avgPrice = currentSellingHolding.average_buy_price;
  const userVirtualCash = userPortfolioSummary ? userPortfolioSummary.virtual_cash : 10000.0;

  let isValid = true;
  let errorMsg = '';

  if (isNaN(qty) || qty <= 0) {
    isValid = false;
    errorMsg = 'Please enter a valid positive whole number of shares.';
  } else if (qty > owned) {
    isValid = false;
    errorMsg = `Cannot sell more shares than owned. You have ${owned} share(s).`;
  }

  if (!isValid) {
    if (errorBox) {
      errorBox.textContent = errorMsg;
      errorBox.style.display = 'block';
    }
    if (confirmBtn) confirmBtn.disabled = true;
    return;
  }

  if (errorBox) errorBox.style.display = 'none';
  if (confirmBtn) confirmBtn.disabled = false;

  const grossVal = Math.round(currentPrice * qty * 100) / 100;
  const costBasis = Math.round(avgPrice * qty * 100) / 100;
  const realizedPnl = Math.round((grossVal - costBasis) * 100) / 100;
  const remaining = owned - qty;
  const projectedCash = Math.round((userVirtualCash + grossVal) * 100) / 100;

  document.getElementById('sell-calc-total-value').textContent = `₹${grossVal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  document.getElementById('sell-calc-cost-basis').textContent = `₹${costBasis.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  
  const pnlDisp = document.getElementById('sell-calc-realized-pnl');
  const isProfit = (realizedPnl >= 0);
  const pnlSign = isProfit ? '+' : '';
  pnlDisp.textContent = `${pnlSign}₹${realizedPnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  pnlDisp.className = `fw-bold num-mono ${isProfit ? 'text-success' : 'text-danger'}`;

  document.getElementById('sell-calc-remaining-qty').textContent = remaining;
  document.getElementById('sell-calc-projected-cash').textContent = `₹${projectedCash.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/**
 * Attaches modal calculation and confirmation event listeners
 */
function setupSellModalEvents() {
  const qtyInput = document.getElementById('sell-quantity-input');
  if (qtyInput) {
    qtyInput.addEventListener('input', updateSellModalCalculations);
  }

  const maxBtn = document.getElementById('sell-modal-max-btn');
  if (maxBtn) {
    maxBtn.addEventListener('click', () => {
      if (currentSellingHolding) {
        qtyInput.value = currentSellingHolding.quantity;
        updateSellModalCalculations();
      }
    });
  }

  const confirmBtn = document.getElementById('confirm-sell-btn');
  if (confirmBtn) {
    confirmBtn.addEventListener('click', handleConfirmSell);
  }
}

/**
 * Sends authenticated SELL request to backend
 */
async function handleConfirmSell() {
  if (!currentSellingHolding) return;

  const qtyInput = document.getElementById('sell-quantity-input');
  const confirmBtn = document.getElementById('confirm-sell-btn');
  const spinner = document.getElementById('confirm-sell-spinner');
  const errorBox = document.getElementById('sell-modal-error');
  const qty = parseInt(qtyInput.value, 10);

  if (isNaN(qty) || qty <= 0 || qty > currentSellingHolding.quantity) {
    if (errorBox) {
      errorBox.textContent = `Please enter a quantity between 1 and ${currentSellingHolding.quantity}.`;
      errorBox.style.display = 'block';
    }
    return;
  }

  try {
    confirmBtn.disabled = true;
    if (spinner) spinner.style.display = 'inline-block';
    if (errorBox) errorBox.style.display = 'none';

    const res = await API.request('/api/portfolio/sell', {
      method: 'POST',
      body: JSON.stringify({
        symbol: currentSellingHolding.symbol,
        quantity: qty
      })
    });

    if (spinner) spinner.style.display = 'none';
    confirmBtn.disabled = false;

    // Close modal
    const modalEl = document.getElementById('sellStockModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();

    // Show success message
    const pnl = res.data && res.data.realized_pnl !== undefined ? res.data.realized_pnl : 0;
    const pnlSign = pnl >= 0 ? '+' : '';
    showToast(`Order executed: Sold ${qty} share(s) of ${currentSellingHolding.symbol}. Realized P&L: ${pnlSign}₹${pnl.toFixed(2)}`, 'success');

    // Reload portfolio summary and transactions
    await Promise.all([
      loadPortfolioSummary(),
      loadTransactions()
    ]);

  } catch (err) {
    if (spinner) spinner.style.display = 'none';
    confirmBtn.disabled = false;
    if (errorBox) {
      errorBox.textContent = err.message || 'Failed to execute sell order. Please try again.';
      errorBox.style.display = 'block';
    }
  }
}
