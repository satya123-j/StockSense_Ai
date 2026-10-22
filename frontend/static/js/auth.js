/**
 * StockSense AI - Client Authentication Handler
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Check auth state on page load and update UI header
  const token = API.getToken();
  const isAuthPage = window.location.pathname.includes('/login') || window.location.pathname.includes('/register');

  if (token && !isAuthPage) {
    try {
      const res = await API.request('/api/auth/me');
      if (res && res.data) {
        updateUserUI(res.data);
      }
    } catch (e) {
      console.warn('Session check failed:', e);
    }
  } else if (!token && !isAuthPage) {
    // Redirect unauthenticated user to login
    window.location.href = '/login';
  }

  // Setup Login Form if present
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = loginForm.querySelector('button[type="submit"]');
      const errorAlert = document.getElementById('auth-error-alert');
      
      const identifier = document.getElementById('identifier').value.trim();
      const password = document.getElementById('password').value;
      const roleElem = document.getElementById('login-role');
      const role = roleElem ? roleElem.value : 'user';

      if (!identifier || !password) {
        showAuthError('Please fill in all fields.');
        return;
      }

      try {
        btn.disabled = true;
        btn.textContent = 'Authenticating...';
        if (errorAlert) errorAlert.style.display = 'none';

        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identifier, password, role })
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.message || 'Login failed.');
        }

        API.setToken(data.data.token);
        showToast('Login successful! Redirecting...', 'success');
        setTimeout(() => {
          if (data.data.redirect_url) {
            window.location.href = data.data.redirect_url;
          } else if (data.data.user && data.data.user.role === 'admin') {
            window.location.href = '/admin';
          } else {
            window.location.href = '/dashboard';
          }
        }, 600);

      } catch (err) {
        showAuthError(err.message);
        btn.disabled = false;
        btn.textContent = (role === 'admin') ? 'Sign In as Admin' : 'Sign In as User';
      }
    });
  }

  // Setup Register Form if present
  const registerForm = document.getElementById('register-form');
  if (registerForm) {
    registerForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = registerForm.querySelector('button[type="submit"]');
      const fullName = document.getElementById('full_name').value.trim();
      const username = document.getElementById('username').value.trim();
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
      const confirmPassword = document.getElementById('confirm_password').value;

      if (password !== confirmPassword) {
        showAuthError('Passwords do not match.');
        return;
      }

      try {
        btn.disabled = true;
        btn.textContent = 'Creating Account...';

        const res = await fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            full_name: fullName,
            username,
            email,
            password
          })
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.message || 'Registration failed.');
        }

        API.setToken(data.data.token);
        showToast('Account created successfully! Welcome to StockSense AI.', 'success');
        setTimeout(() => {
          window.location.href = '/dashboard';
        }, 800);

      } catch (err) {
        showAuthError(err.message);
        btn.disabled = false;
        btn.textContent = 'Create Account';
      }
    });
  }
});

function showAuthError(msg) {
  const alert = document.getElementById('auth-error-alert');
  if (alert) {
    alert.textContent = msg;
    alert.style.display = 'block';
  } else {
    showToast(msg, 'error');
  }
}

function updateUserUI(user) {
  const userNameElem = document.getElementById('sidebar-user-name');
  const userAvatarElem = document.getElementById('sidebar-user-avatar');
  const userStatusElem = document.querySelector('.user-status-text');
  const walletChip = document.getElementById('topbar-wallet-chip');
  const walletBalElem = document.getElementById('topbar-virtual-balance');

  if (userNameElem) {
    userNameElem.textContent = user.full_name || user.username;
  }
  if (userAvatarElem) {
    const initials = (user.full_name || user.username).substring(0, 2).toUpperCase();
    userAvatarElem.textContent = initials;
  }
  if (userStatusElem) {
    userStatusElem.textContent = (user.role === 'admin') ? 'Administrator' : 'NSE / BSE Member';
  }
  if (walletBalElem && user.virtual_cash !== undefined) {
    walletBalElem.textContent = typeof formatINR === 'function' ? formatINR(user.virtual_cash) : '₹' + Number(user.virtual_cash).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  }
  if (walletChip && user.role === 'admin') {
    walletChip.style.display = 'none';
  }
}

// Global logout action
async function handleLogout() {
  try {
    await fetch('/api/auth/logout', { method: 'POST' });
  } catch (e) {
    console.warn(e);
  }
  API.removeToken();
  window.location.href = '/login';
}

// Global Search Autocomplete Setup
function setupSearchAutocomplete(inputId, dropdownId, onSelect) {
  const input = document.getElementById(inputId);
  const dropdown = document.getElementById(dropdownId);
  if (!input || !dropdown) return;

  let debounceTimer;

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const query = input.value.trim();

    if (query.length < 1) {
      dropdown.style.display = 'none';
      dropdown.innerHTML = '';
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await API.request(`/api/stocks/search?q=${encodeURIComponent(query)}&limit=6`);
        if (!res || !res.data || res.data.length === 0) {
          dropdown.innerHTML = `<div class="p-3 text-muted text-center" style="font-size:0.8rem;">No Indian securities found for "${query}"</div>`;
          dropdown.style.display = 'block';
          return;
        }

        dropdown.innerHTML = '';
        res.data.forEach(stock => {
          const item = document.createElement('div');
          item.className = 'search-dropdown-item';
          item.innerHTML = `
            <div>
              <div class="search-item-ticker num-mono">${stock.symbol}</div>
              <div class="search-item-desc">${stock.name}</div>
            </div>
            <span class="stock-card-badge">${stock.exchange || 'NSE'}</span>
          `;
          item.addEventListener('click', () => {
            dropdown.style.display = 'none';
            input.value = '';
            if (typeof onSelect === 'function') {
              onSelect(stock);
            } else {
              window.location.href = `/analysis/${encodeURIComponent(stock.symbol)}`;
            }
          });
          dropdown.appendChild(item);
        });

        dropdown.style.display = 'block';
      } catch (e) {
        console.error('Search error:', e);
      }
    }, 180);
  });

  // Close dropdown on outside click
  document.addEventListener('click', (e) => {
    if (!input.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.style.display = 'none';
    }
  });

  // Handle Enter key on search input
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const query = input.value.trim().toUpperCase();
      if (query.length >= 1) {
        dropdown.style.display = 'none';
        if (typeof onSelect === 'function') {
          onSelect({ symbol: query });
        } else {
          window.location.href = `/analysis/${encodeURIComponent(query)}`;
        }
      }
    }
  });
}

// Automatically bind global topbar search on all pages
document.addEventListener('DOMContentLoaded', () => {
  setupSearchAutocomplete('top-header-search-input', 'top-header-search-results');
});
