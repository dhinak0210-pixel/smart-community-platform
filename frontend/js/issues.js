/**
 * Issues CRUD & UI Event Handler Module
 */

document.addEventListener('DOMContentLoaded', () => {
  MapManager.initMap();
  loadIssues();
  updateAuthUI();

  // Handle Issue Submission
  const formReport = document.getElementById('formReportIssue');
  if (formReport) {
    formReport.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!Auth.isAuthenticated()) {
        alert('Please login first to submit an issue report.');
        return;
      }

      const issuePayload = {
        title: document.getElementById('issueTitle').value,
        category: document.getElementById('issueCategory').value,
        priority: document.getElementById('issuePriority').value,
        latitude: parseFloat(document.getElementById('issueLat').value),
        longitude: parseFloat(document.getElementById('issueLng').value),
        address: document.getElementById('issueAddress').value,
        description: document.getElementById('issueDescription').value,
      };

      try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/issues/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...Auth.getAuthHeader(),
          },
          body: JSON.stringify(issuePayload),
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Failed to submit issue');

        // Reset form & hide modal
        formReport.reset();
        const modalEl = document.getElementById('reportIssueModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();

        loadIssues(); // Reload feed & map markers
      } catch (err) {
        alert(`Error: ${err.message}`);
      }
    });
  }

  // Handle Login Form
  const formLogin = document.getElementById('formLogin');
  if (formLogin) {
    formLogin.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('loginEmail').value;
      const password = document.getElementById('loginPassword').value;

      try {
        await Auth.login(email, password);
        const modalEl = document.getElementById('loginModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
        updateAuthUI();
      } catch (err) {
        alert(`Login failed: ${err.message}`);
      }
    });
  }

  // Handle Register Form
  const formRegister = document.getElementById('formRegister');
  if (formRegister) {
    formRegister.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fullName = document.getElementById('regFullName').value;
      const email = document.getElementById('regEmail').value;
      const password = document.getElementById('regPassword').value;
      const role = document.getElementById('regRole').value;

      try {
        await Auth.register(fullName, email, password, role);
        alert('Registration successful! Please login.');
        const modalEl = document.getElementById('registerModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      } catch (err) {
        alert(`Registration failed: ${err.message}`);
      }
    });
  }
});

async function loadIssues() {
  const feedList = document.getElementById('issueFeedList');
  const countBadge = document.getElementById('activeIssueCount');

  try {
    const response = await fetch(`${CONFIG.API_BASE_URL}/issues/`);
    const issues = await response.json();

    if (countBadge) countBadge.textContent = `${issues.length} Issues Loaded`;

    MapManager.renderIssueMarkers(issues);

    if (!feedList) return;

    if (issues.length === 0) {
      feedList.innerHTML = '<div class="text-center text-muted py-4">No community issues reported yet. Be the first to report!</div>';
      return;
    }

    feedList.innerHTML = issues.map(issue => `
      <div class="glass-card p-3 mb-3 border-0 bg-dark bg-opacity-50">
        <div class="d-flex justify-content-between align-items-start mb-2">
          <h6 class="fw-bold mb-0 text-white">${issue.title}</h6>
          <span class="badge badge-${issue.status}">${issue.status.replace('_', ' ')}</span>
        </div>
        <p class="small text-secondary mb-2">${issue.description.substring(0, 100)}...</p>
        <div class="d-flex justify-content-between align-items-center small text-muted">
          <span><i class="bi bi-tag-fill me-1"></i>${issue.category}</span>
          <button class="btn btn-sm btn-outline-primary py-0 px-2" onclick="upvoteIssue(${issue.id})">
            <i class="bi bi-hand-thumbs-up-fill me-1"></i>${issue.vote_count}
          </button>
        </div>
      </div>
    `).join('');

  } catch (err) {
    if (feedList) feedList.innerHTML = `<div class="text-danger p-3">Failed to load issues from server.</div>`;
  }
}

async function upvoteIssue(issueId) {
  if (!Auth.isAuthenticated()) {
    alert('Please login to upvote issues.');
    return;
  }
  try {
    await fetch(`${CONFIG.API_BASE_URL}/issues/${issueId}/vote`, {
      method: 'POST',
      headers: Auth.getAuthHeader(),
    });
    loadIssues();
  } catch (err) {
    console.error('Vote failed:', err);
  }
}

function updateAuthUI() {
  const authNav = document.getElementById('authNavButtons');
  const user = Auth.getUser();

  if (authNav && user) {
    authNav.innerHTML = `
      <span class="text-light small me-2"><i class="bi bi-person-circle me-1"></i>${user.full_name} (${user.role})</span>
      <button class="btn btn-outline-danger btn-sm" onclick="Auth.logout()">Logout</button>
    `;
  }
}
