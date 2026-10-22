/**
 * StockSense AI - Unified API Client & Utilities
 */

const API = {
  getToken() {
    let token = localStorage.getItem('jwt_token');
    if (!token && typeof document !== 'undefined') {
      const match = document.cookie.match(/(?:^|; )jwt_token=([^;]*)/);
      if (match && match[1]) {
        token = decodeURIComponent(match[1]);
        try { localStorage.setItem('jwt_token', token); } catch (e) {}
      }
    }
    return token || null;
  },

  setToken(token) {
    if (token) {
      localStorage.setItem('jwt_token', token);
      document.cookie = `jwt_token=${token}; path=/; max-age=${7 * 24 * 3600}; SameSite=Lax`;
    }
  },

  removeToken() {
    localStorage.removeItem('jwt_token');
    document.cookie = 'jwt_token=; path=/; max-age=0; SameSite=Lax';
  },

  async request(endpoint, options = {}) {
    const token = this.getToken();
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(endpoint, {
        ...options,
        headers
      });

      const data = await response.json().catch(() => ({}));

      if (response.status === 401) {
        // Token invalid or expired
        this.removeToken();
        if (!window.location.pathname.includes('/login') && !window.location.pathname.includes('/register')) {
          window.location.href = '/login?expired=1';
        }
        throw new Error(data.message || 'Session expired. Please log in again.');
      }

      if (!response.ok) {
        throw new Error(data.message || `Request failed with status ${response.status}`);
      }

      return data;
    } catch (err) {
      console.error(`API Error [${endpoint}]:`, err);
      throw err;
    }
  }
};

// Notification Toast Utility
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `fintech-toast toast-${type}`;
  
  let iconSvg = 'ℹ️';
  if (type === 'success') iconSvg = '✅';
  if (type === 'error') iconSvg = '⚠️';

  toast.innerHTML = `
    <span>${iconSvg}</span>
    <div style="flex-grow: 1;">${message}</div>
    <button style="background:none;border:none;color:#94a3b8;cursor:pointer;" onclick="this.parentElement.remove()">✕</button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Currency / Numeric Formatters
function formatINR(num) {
  if (num === null || num === undefined || isNaN(num)) return '₹0.00';
  return '₹' + Number(num).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function formatLargeINR(num) {
  if (num === null || num === undefined || isNaN(num)) return 'N/A';
  const val = Number(num);
  if (Math.abs(val) >= 1e7) {
    return '₹' + (val / 1e7).toFixed(2) + ' Cr';
  } else if (Math.abs(val) >= 1e5) {
    return '₹' + (val / 1e5).toFixed(2) + ' L';
  }
  return formatINR(val);
}

function formatPercent(val) {
  if (val === null || val === undefined || isNaN(val)) return '0.00%';
  const num = Number(val);
  const prefix = num > 0 ? '+' : '';
  return `${prefix}${num.toFixed(2)}%`;
}
