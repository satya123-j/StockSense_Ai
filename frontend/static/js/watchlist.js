/**
 * StockSense AI - Watchlist Management Logic (Light Mode)
 */

let watchlistItems = [];

document.addEventListener('DOMContentLoaded', () => {
  loadWatchlist();
  setupAddStockModal();
  setupWatchlistFilter();
});

async function loadWatchlist() {
  const tableBody = document.getElementById('watchlist-table-body');
  const emptyState = document.getElementById('watchlist-empty-state');
  if (!tableBody) return;

  try {
    const res = await API.request('/api/watchlist');
    if (!res || !res.data) return;

    watchlistItems = res.data;
    renderWatchlistSummary(watchlistItems);

    if (watchlistItems.length === 0) {
      tableBody.innerHTML = '';
      if (emptyState) emptyState.style.display = 'block';
      return;
    }

    if (emptyState) emptyState.style.display = 'none';
    renderTableRows(watchlistItems);

  } catch (err) {
    console.error('Error loading watchlist:', err);
    showToast('Failed to load watchlist.', 'error');
  }
}

function renderTableRows(items) {
  const tableBody = document.getElementById('watchlist-table-body');
  if (!tableBody) return;

  tableBody.innerHTML = '';
  items.forEach(item => {
    const isPositive = (item.change >= 0);
    const deltaClass = isPositive ? 'positive' : 'negative';
    const deltaIcon = isPositive ? '▲' : '▼';
    const demoBadge = item.is_demo ? '<span class="stock-card-badge ms-1" style="color:#d97706;">DEMO</span>' : '';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>
        <div class="fw-bold num-mono" style="color: #111827;">${item.symbol} ${demoBadge}</div>
        <div class="text-secondary" style="font-size:0.75rem;">${item.company_name}</div>
      </td>
      <td>
        <span class="stock-card-badge">${item.exchange || 'NSE'}</span>
      </td>
      <td>
        <span class="text-secondary" style="font-size:0.8rem;">${item.sector || 'Equity'}</span>
      </td>
      <td class="fw-bold num-mono" style="color: #111827;">
        ${formatINR(item.current_price)}
      </td>
      <td>
        <span class="delta-pill ${deltaClass} num-mono">
          ${deltaIcon} ${formatPercent(item.change_percent)}
        </span>
      </td>
      <td class="text-secondary num-mono" style="font-size:0.8rem;">
        ${formatINR(item.day_low)} - ${formatINR(item.day_high)}
      </td>
      <td>
        <div class="d-flex align-items-center gap-2">
          <a href="/analysis/${encodeURIComponent(item.symbol)}" class="btn-fintech btn-fintech-ghost" style="padding:2px 8px; font-size:0.75rem;">
            Analyze →
          </a>
          <button class="btn-fintech btn-fintech-danger" style="padding:2px 8px; font-size:0.75rem;" onclick="removeWatchlistItem(${item.id}, '${item.symbol}')">
            Remove
          </button>
        </div>
      </td>
    `;
    tableBody.appendChild(tr);
  });
}

function renderWatchlistSummary(items) {
  document.getElementById('summary-total-count').textContent = items.length;

  if (items.length === 0) {
    document.getElementById('summary-top-gainer').textContent = 'N/A';
    document.getElementById('summary-top-loser').textContent = 'N/A';
    return;
  }

  // Find Top Gainer and Loser
  const sorted = [...items].sort((a, b) => b.change_percent - a.change_percent);
  const topGainer = sorted[0];
  const topLoser = sorted[sorted.length - 1];

  const gainerElem = document.getElementById('summary-top-gainer');
  if (topGainer && topGainer.change_percent > 0) {
    gainerElem.innerHTML = `<span class="text-success fw-bold num-mono">${topGainer.symbol} (+${topGainer.change_percent.toFixed(2)}%)</span>`;
  } else {
    gainerElem.textContent = 'None';
  }

  const loserElem = document.getElementById('summary-top-loser');
  if (topLoser && topLoser.change_percent < 0) {
    loserElem.innerHTML = `<span class="text-danger fw-bold num-mono">${topLoser.symbol} (${topLoser.change_percent.toFixed(2)}%)</span>`;
  } else {
    loserElem.textContent = 'None';
  }
}

async function removeWatchlistItem(id, symbol) {
  if (!confirm(`Remove ${symbol} from your watchlist?`)) return;

  try {
    await API.request(`/api/watchlist/${encodeURIComponent(symbol)}`, { method: 'DELETE' });
    showToast(`Removed ${symbol} from watchlist.`, 'info');
    loadWatchlist();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function setupWatchlistFilter() {
  const filterInput = document.getElementById('watchlist-filter-input');
  if (!filterInput) return;

  filterInput.addEventListener('input', () => {
    const q = filterInput.value.toLowerCase().trim();
    const filtered = watchlistItems.filter(item => 
      item.symbol.toLowerCase().includes(q) || 
      item.company_name.toLowerCase().includes(q) ||
      (item.sector && item.sector.toLowerCase().includes(q))
    );
    renderTableRows(filtered);
  });
}

function setupAddStockModal() {
  const searchInput = document.getElementById('modal-stock-search-input');
  const searchResults = document.getElementById('modal-search-results');

  if (!searchInput || !searchResults) return;

  let debounceTimer;
  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const q = searchInput.value.trim();

    if (q.length < 1) {
      searchResults.innerHTML = '';
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await API.request(`/api/stocks/search?q=${encodeURIComponent(q)}&limit=5`);
        if (!res || !res.data || res.data.length === 0) {
          searchResults.innerHTML = `<div class="p-3 text-secondary text-center" style="font-size:0.8rem;">No securities found</div>`;
          return;
        }

        searchResults.innerHTML = '';
        res.data.forEach(stock => {
          const item = document.createElement('div');
          item.className = 'd-flex align-items-center justify-content-between p-2 border-bottom border-default';
          item.innerHTML = `
            <div>
              <div class="fw-bold num-mono" style="font-size:0.85rem; color: #111827;">${stock.symbol}</div>
              <div class="text-secondary" style="font-size:0.75rem;">${stock.name}</div>
            </div>
            <button class="btn-fintech btn-fintech-primary" style="font-size:0.75rem; padding:2px 8px;">
              + Add
            </button>
          `;
          item.querySelector('button').addEventListener('click', async (e) => {
            e.stopPropagation();
            try {
              await API.request('/api/watchlist', {
                method: 'POST',
                body: JSON.stringify({
                  symbol: stock.symbol,
                  company_name: stock.name
                })
              });
              showToast(`Added ${stock.symbol} to watchlist!`, 'success');
              searchInput.value = '';
              searchResults.innerHTML = '';
              const modalElem = document.getElementById('addStockModal');
              const modalInstance = bootstrap.Modal.getInstance(modalElem);
              if (modalInstance) modalInstance.hide();
              loadWatchlist();
            } catch (err) {
              showToast(err.message, 'error');
            }
          });
          searchResults.appendChild(item);
        });

      } catch (err) {
        console.error(err);
      }
    }, 180);
  });
}
