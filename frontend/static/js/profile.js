/**
 * StockSense AI - User Profile & Account Settings Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  loadUserProfile();
  setupProfileUpdateForm();
  setupChangePasswordForm();
});

async function loadUserProfile() {
  try {
    const res = await API.request('/api/user/profile');
    if (!res || !res.data) return;

    const user = res.data;
    document.getElementById('profile-username').textContent = user.username;
    document.getElementById('profile-email').textContent = user.email;
    document.getElementById('profile-fullname-display').textContent = user.full_name || user.username;
    document.getElementById('profile-joined').textContent = user.created_at ? new Date(user.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : 'Recently';
    document.getElementById('profile-watchlist-count').textContent = user.watchlist_count || 0;

    // Fill form inputs
    const fullNameInput = document.getElementById('edit-full-name');
    const emailInput = document.getElementById('edit-email');
    if (fullNameInput) fullNameInput.value = user.full_name || '';
    if (emailInput) emailInput.value = user.email || '';

  } catch (err) {
    console.error('Failed to load profile:', err);
    showToast('Unable to load profile information.', 'error');
  }
}

function setupProfileUpdateForm() {
  const form = document.getElementById('profile-update-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    const fullName = document.getElementById('edit-full-name').value.trim();
    const email = document.getElementById('edit-email').value.trim();

    try {
      btn.disabled = true;
      btn.textContent = 'Saving Changes...';

      const res = await API.request('/api/user/profile', {
        method: 'PUT',
        body: JSON.stringify({ full_name: fullName, email })
      });

      showToast('Profile updated successfully!', 'success');
      loadUserProfile();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Save Changes';
    }
  });
}

function setupChangePasswordForm() {
  const form = document.getElementById('change-password-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-new-password').value;

    if (newPassword !== confirmPassword) {
      showToast('New passwords do not match.', 'error');
      return;
    }

    try {
      btn.disabled = true;
      btn.textContent = 'Updating Password...';

      await API.request('/api/user/change-password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword
        })
      });

      showToast('Password changed successfully!', 'success');
      form.reset();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Update Password';
    }
  });
}
