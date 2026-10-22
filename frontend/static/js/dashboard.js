/**
 * StockSense AI - Dashboard Logic (Light Mode)
 */

document.addEventListener('DOMContentLoaded', () => {
  loadMarketIndices();
  loadWatchlistStockCards();
  loadRecentViewsCards();
  setupSearchAutocomplete('dashboard-search-input', 'dashboard-search-results');
});

// 1. Render Major Benchmark Indices Cards
async function loadMarketIndices() {
  const container = document.getElementById('market-indices-grid');
  if (!container) return;

  try {
    const res = await API.request('/api/market/indices');
    if (!res || !res.data || res.data.length === 0) return;

    container.innerHTML = '';
    res.data.forEach(idx => {
      const isPositive = (idx.change >= 0);
      const deltaClass = isPositive ? 'positive' : 'negative';
      const deltaIcon = isPositive ? '▲' : '▼';

      const priceVal = (idx.current_price !== undefined && idx.current_price !== null && idx.current_price !== '')
        ? idx.current_price
        : idx.price;
      const formattedPrice = (priceVal !== undefined && priceVal !== null && Number(priceVal) > 0)
        ? Number(priceVal).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
        : '--';

      const card = document.createElement('div');
      card.className = 'market-index-card';
      card.innerHTML = `
        <div class="index-header">
          <span class="index-label">${idx.name || idx.symbol}</span>
          <span class="delta-pill ${deltaClass} num-mono">
            ${deltaIcon} ${formatPercent(idx.change_percent)}
          </span>
        </div>
        <div class="index-val num-mono">${formattedPrice}</div>
        <div class="d-flex justify-content-between align-items-center" style="font-size:0.75rem;">
          <span class="text-secondary num-mono">${isPositive ? '+' : ''}${Number(idx.change || 0).toFixed(2)} pts</span>
          <span class="stock-card-badge">${idx.exchange || 'NSE'}</span>
        </div>
      `;
      container.appendChild(card);
    });

  } catch (err) {
    console.error('Error loading market indices:', err);
  }
}

// 2. Render Watchlist Stock Cards
async function loadWatchlistStockCards() {
  const container = document.getElementById('watchlist-cards-container');
  if (!container) return;

  try {
    const res = await API.request('/api/watchlist');
    if (!res || !res.data || res.data.length === 0) {
      container.innerHTML = `
        <div class="col-12 text-center py-4 w-100" style="grid-column: 1 / -1;">
          <div class="text-secondary mb-2" style="font-size:0.825rem;">No stocks saved in your watchlist.</div>
          <a href="/watchlist" class="btn-fintech btn-fintech-ghost" style="font-size:0.75rem; padding:3px 10px;">
            + Add First Stock
          </a>
        </div>
      `;
      return;
    }

    container.innerHTML = '';
    res.data.slice(0, 6).forEach(item => {
      const isPositive = (item.change >= 0);
      const deltaClass = isPositive ? 'positive' : 'negative';
      const deltaIcon = isPositive ? '▲' : '▼';

      const card = document.createElement('a');
      card.href = `/analysis/${encodeURIComponent(item.symbol)}`;
      card.className = 'stock-card';
      card.innerHTML = `
        <div class="stock-card-top">
          <div>
            <div class="stock-card-symbol num-mono">${item.symbol}</div>
            <div class="stock-card-name">${item.company_name}</div>
          </div>
          <span class="stock-card-badge">${item.exchange || 'NSE'}</span>
        </div>
        <div class="stock-card-bottom">
          <div class="stock-card-price num-mono">${formatINR(item.current_price)}</div>
          <span class="delta-pill ${deltaClass} num-mono">
            ${deltaIcon} ${formatINR(Math.abs(item.change))} (${formatPercent(item.change_percent)})
          </span>
        </div>
      `;
      container.appendChild(card);
    });

  } catch (err) {
    console.error('Error loading watchlist cards:', err);
  }
}

// 3. Render Recently Viewed Stock Cards
async function loadRecentViewsCards() {
  const container = document.getElementById('recent-views-cards-container');
  if (!container) return;

  try {
    const res = await API.request('/api/user/recent-views');
    if (!res || !res.data || res.data.length === 0) {
      container.innerHTML = `
        <div class="text-secondary p-3 text-center w-100" style="grid-column: 1 / -1; font-size:0.8rem;">
          No recently viewed stocks yet. Search for any stock above!
        </div>
      `;
      return;
    }

    container.innerHTML = '';
    res.data.slice(0, 4).forEach(item => {
      const card = document.createElement('a');
      card.href = `/analysis/${encodeURIComponent(item.symbol)}`;
      card.className = 'stock-card';
      card.innerHTML = `
        <div class="stock-card-top">
          <div>
            <div class="stock-card-symbol num-mono">${item.symbol}</div>
            <div class="stock-card-name">${item.company_name || item.symbol}</div>
          </div>
          <span class="stock-card-badge">NSE</span>
        </div>
        <div class="d-flex justify-content-between align-items-center mt-2">
          <span class="text-secondary" style="font-size:0.7rem;">Click to analyze</span>
          <span class="btn-fintech btn-fintech-ghost" style="padding:1px 6px; font-size:0.7rem;">View →</span>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading recent views:', err);
  }
}
