/**
 * Smart Community Platform - UI Components
 * Toast notifications, loaders, modals, and shared render helpers.
 */

/* ================================================================
   TOAST NOTIFICATION SYSTEM
   ================================================================ */
const Toast = {
  _container: null,

  init() {
    if (this._container) return;
    this._container = document.createElement("div");
    this._container.id = "toast-container";
    this._container.className = "toast-container";
    document.body.appendChild(this._container);
  },

  show(message, type, duration) {
    this.init();
    type = type || "info";
    duration = duration || CONFIG.TOAST_DURATION_MS;

    const icons = {
      success: "bi-check-circle-fill",
      error: "bi-x-circle-fill",
      warning: "bi-exclamation-triangle-fill",
      info: "bi-info-circle-fill"
    };
    const colors = {
      success: "var(--color-success)",
      error: "var(--color-danger)",
      warning: "var(--color-warning)",
      info: "var(--color-info)"
    };

    const el = document.createElement("div");
    el.className = "toast-item toast-" + type;
    el.style.borderLeftColor = colors[type] || colors.info;
    el.innerHTML =
      '<div class="toast-icon"><i class="bi ' + (icons[type] || icons.info) + '" style="color:' + (colors[type] || colors.info) + '"></i></div>' +
      '<div class="toast-body">' + this._escapeHtml(message) + '</div>' +
      '<button class="toast-close" aria-label="Close"><i class="bi bi-x"></i></button>';

    el.querySelector(".toast-close").addEventListener("click", () => this._dismiss(el));
    this._container.appendChild(el);
    requestAnimationFrame(() => el.classList.add("toast-visible"));
    const timer = setTimeout(() => this._dismiss(el), duration);
    el._timer = timer;
    return el;
  },

  _dismiss(el) {
    if (el._dismissed) return;
    el._dismissed = true;
    clearTimeout(el._timer);
    el.classList.remove("toast-visible");
    el.classList.add("toast-exit");
    setTimeout(() => el.remove(), 300);
  },

  _escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  },

  success(msg, dur) { return this.show(msg, "success", dur); },
  error(msg, dur)   { return this.show(msg, "error", dur || 6000); },
  warning(msg, dur) { return this.show(msg, "warning", dur); },
  info(msg, dur)    { return this.show(msg, "info", dur); }
};

/* ================================================================
   LOADING STATE MANAGER
   ================================================================ */
const Loader = {
  show() {
    if (document.getElementById("page-loader")) return;
    const ov = document.createElement("div");
    ov.id = "page-loader";
    ov.className = "page-loader";
    ov.innerHTML = '<div class="loader-spinner"></div>';
    document.body.appendChild(ov);
    requestAnimationFrame(() => ov.classList.add("visible"));
  },

  hide() {
    const ov = document.getElementById("page-loader");
    if (!ov) return;
    ov.classList.remove("visible");
    setTimeout(() => ov.remove(), 300);
  },

  setButtonLoading(button, text) {
    text = text || "Loading...";
    const origHtml = button.innerHTML;
    const origDisabled = button.disabled;
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>' + text;
    return function restore() {
      button.innerHTML = origHtml;
      button.disabled = origDisabled;
    };
  },

  showSkeleton(container, rows) {
    rows = rows || 3;
    container.innerHTML = "";
    for (let i = 0; i < rows; i++) {
      const sk = document.createElement("div");
      sk.className = "skeleton-card";
      sk.innerHTML =
        '<div class="skeleton-line skeleton-line-lg"></div>' +
        '<div class="skeleton-line skeleton-line-md"></div>' +
        '<div class="skeleton-line skeleton-line-sm"></div>';
      container.appendChild(sk);
    }
  },

  hideSkeleton(container) {
    const cards = container.querySelectorAll(".skeleton-card");
    cards.forEach((c) => c.remove());
  }
};

/* ================================================================
   MODAL MANAGER
   ================================================================ */
const Modal = {
  confirm(title, message, confirmText, dangerMode) {
    confirmText = confirmText || "Confirm";
    return new Promise((resolve) => {
      const id = "modal-confirm-" + Date.now();
      const btnClass = dangerMode ? "btn-danger" : "btn-primary";
      const html =
        '<div class="modal fade" id="' + id + '" tabindex="-1" data-bs-backdrop="static">' +
        '<div class="modal-dialog modal-dialog-centered"><div class="modal-content">' +
        '<div class="modal-header"><h5 class="modal-title">' + title + '</h5>' +
        '<button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>' +
        '<div class="modal-body"><p>' + message + '</p></div>' +
        '<div class="modal-footer">' +
        '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>' +
        '<button type="button" class="btn ' + btnClass + '" id="' + id + '-yes">' + confirmText + '</button>' +
        '</div></div></div></div>';
      document.body.insertAdjacentHTML("beforeend", html);
      const el = document.getElementById(id);
      const bsModal = new bootstrap.Modal(el);
      el.querySelector("#" + id + "-yes").addEventListener("click", () => { bsModal.hide(); resolve(true); });
      el.addEventListener("hidden.bs.modal", () => { el.remove(); resolve(false); }, { once: true });
      bsModal.show();
    });
  },

  alert(title, message, type) {
    type = type || "info";
    const icons = { success: "bi-check-circle", error: "bi-x-circle", warning: "bi-exclamation-triangle", info: "bi-info-circle" };
    return new Promise((resolve) => {
      const id = "modal-alert-" + Date.now();
      const html =
        '<div class="modal fade" id="' + id + '" tabindex="-1">' +
        '<div class="modal-dialog modal-dialog-centered"><div class="modal-content">' +
        '<div class="modal-header"><h5 class="modal-title"><i class="bi ' + (icons[type] || icons.info) + ' me-2"></i>' + title + '</h5>' +
        '<button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>' +
        '<div class="modal-body"><p>' + message + '</p></div>' +
        '<div class="modal-footer"><button type="button" class="btn btn-primary" data-bs-dismiss="modal">OK</button></div>' +
        '</div></div></div>';
      document.body.insertAdjacentHTML("beforeend", html);
      const el = document.getElementById(id);
      const bsModal = new bootstrap.Modal(el);
      el.addEventListener("hidden.bs.modal", () => { el.remove(); resolve(); }, { once: true });
      bsModal.show();
    });
  },

  showImage(imageUrl, title) {
    title = title || "";
    const id = "modal-img-" + Date.now();
    const html =
      '<div class="modal fade" id="' + id + '" tabindex="-1">' +
      '<div class="modal-dialog modal-dialog-centered modal-xl"><div class="modal-content bg-dark">' +
      '<div class="modal-header border-0"><h6 class="modal-title text-white">' + title + '</h6>' +
      '<button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>' +
      '<div class="modal-body text-center p-0"><img src="' + imageUrl + '" class="img-fluid" alt="Preview"></div>' +
      '</div></div></div>';
    document.body.insertAdjacentHTML("beforeend", html);
    const el = document.getElementById(id);
    const bsModal = new bootstrap.Modal(el);
    el.addEventListener("hidden.bs.modal", () => el.remove(), { once: true });
    bsModal.show();
  }
};

/* ================================================================
   SHARED RENDER FUNCTIONS
   ================================================================ */
function renderStatusBadge(status) {
  const color = CONFIG.STATUS_COLORS[status] || "#6B7280";
  const label = CONFIG.STATUS_LABELS[status] || status;
  return '<span class="badge badge-status" style="background-color:' + color + '">' + label + '</span>';
}

function renderPriorityBadge(priority) {
  const color = CONFIG.PRIORITY_COLORS[priority] || "#6B7280";
  const label = CONFIG.PRIORITY_LABELS[priority] || priority;
  const pulse = priority === "critical" ? ' priority-critical' : '';
  return '<span class="badge badge-priority' + pulse + '" style="background-color:' + color + '">' +
    (priority === "critical" ? '<span class="pulse-dot"></span>' : '') + label + '</span>';
}

function renderCategoryBadge(category) {
  const icon = CONFIG.CATEGORY_ICONS[category] || "bi-question-circle";
  const label = CONFIG.CATEGORY_LABELS[category] || category;
  return '<span class="category-badge"><i class="bi ' + icon + '"></i> ' + label + '</span>';
}

function renderTimeAgo(dateString) {
  if (!dateString) return "";
  const now = Date.now();
  const then = new Date(dateString).getTime();
  const diff = Math.max(0, now - then);
  const mins = Math.floor(diff / 60000);
  const hrs = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (mins < 1) return "Just now";
  if (mins < 60) return mins + "m ago";
  if (hrs < 24) return hrs + "h ago";
  if (days === 1) return "Yesterday";
  if (days < 30) return days + "d ago";
  return new Date(dateString).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function renderUserAvatar(user, size) {
  size = size || 40;
  if (!user) return '<div class="avatar-circle" style="width:' + size + 'px;height:' + size + 'px"><i class="bi bi-person"></i></div>';
  if (user.avatar_url) {
    return '<img src="' + user.avatar_url + '" alt="' + (user.name || '') + '" class="avatar-img" style="width:' + size + 'px;height:' + size + 'px" loading="lazy">';
  }
  const name = user.name || "U";
  const initials = name.split(" ").map((w) => w[0]).join("").substring(0, 2).toUpperCase();
  const hue = (name.charCodeAt(0) * 37 + (name.charCodeAt(1) || 0) * 53) % 360;
  return '<div class="avatar-circle" style="width:' + size + 'px;height:' + size + 'px;background:hsl(' + hue + ',55%,50%);font-size:' + Math.round(size * 0.4) + 'px">' + initials + '</div>';
}

function renderIssueCard(issue) {
  const img = issue.image_url
    ? '<div class="issue-card-img" style="background-image:url(' + issue.image_url + ')"></div>'
    : '<div class="issue-card-img issue-card-img-placeholder"><i class="bi ' + (CONFIG.CATEGORY_ICONS[issue.category] || 'bi-geo-alt') + '"></i></div>';
  const addr = issue.location_address || issue.location_city || "Location not specified";
  const aiBadge = issue.ai_processed
    ? '<span class="badge text-white ms-1" style="font-size:0.65rem;background:linear-gradient(135deg,#6366f1,#a855f7)"><i class="bi bi-robot me-1"></i>AI Triaged</span>'
    : '';
  return (
    '<div class="issue-card" data-uuid="' + issue.uuid + '" onclick="window.location.href=\'issue.html?uuid=' + issue.uuid + '\'">' +
    img +
    '<div class="issue-card-body">' +
    '<div class="issue-card-header">' + renderCategoryBadge(issue.category) + aiBadge + renderStatusBadge(issue.status) + '</div>' +
    '<h6 class="issue-card-title">' + escapeHtml(issue.title) + '</h6>' +
    '<p class="issue-card-desc">' + escapeHtml(issue.short_description || '') + '</p>' +
    '<div class="issue-card-meta">' +
    '<span><i class="bi bi-geo-alt"></i> ' + escapeHtml(addr) + '</span>' +
    '<span><i class="bi bi-clock"></i> ' + renderTimeAgo(issue.created_at) + '</span>' +
    '</div>' +
    '<div class="issue-card-footer">' +
    '<div class="issue-card-stats">' +
    '<span><i class="bi bi-hand-thumbs-up"></i> ' + (issue.vote_count || 0) + '</span>' +
    '<span><i class="bi bi-chat"></i> ' + (issue.comment_count || 0) + '</span>' +
    '<span><i class="bi bi-eye"></i> ' + formatNumber(issue.view_count || 0) + '</span>' +
    '</div>' +
    renderPriorityBadge(issue.priority) +
    '</div></div></div>'
  );
}

function renderPagination(currentPage, totalPages, onPageChange) {
  if (totalPages <= 1) return "";
  let html = '<nav aria-label="Page navigation"><ul class="pagination justify-content-center">';
  html += '<li class="page-item' + (currentPage <= 1 ? " disabled" : "") + '"><a class="page-link" href="#" data-page="' + (currentPage - 1) + '"><i class="bi bi-chevron-left"></i></a></li>';

  let start = Math.max(1, currentPage - 2);
  let end = Math.min(totalPages, currentPage + 2);
  if (start > 1) { html += '<li class="page-item"><a class="page-link" href="#" data-page="1">1</a></li>'; if (start > 2) html += '<li class="page-item disabled"><span class="page-link">...</span></li>'; }
  for (let i = start; i <= end; i++) {
    html += '<li class="page-item' + (i === currentPage ? " active" : "") + '"><a class="page-link" href="#" data-page="' + i + '">' + i + '</a></li>';
  }
  if (end < totalPages) { if (end < totalPages - 1) html += '<li class="page-item disabled"><span class="page-link">...</span></li>'; html += '<li class="page-item"><a class="page-link" href="#" data-page="' + totalPages + '">' + totalPages + '</a></li>'; }

  html += '<li class="page-item' + (currentPage >= totalPages ? " disabled" : "") + '"><a class="page-link" href="#" data-page="' + (currentPage + 1) + '"><i class="bi bi-chevron-right"></i></a></li>';
  html += '</ul></nav>';

  const container = document.createElement("div");
  container.innerHTML = html;
  container.querySelectorAll("a.page-link").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const p = parseInt(a.dataset.page);
      if (p >= 1 && p <= totalPages && p !== currentPage) onPageChange(p);
    });
  });
  return container;
}

function formatNumber(num) {
  if (num === null || num === undefined) return "0";
  if (num >= 1000000) return (num / 1000000).toFixed(1).replace(/\.0$/, "") + "M";
  if (num >= 1000) return (num / 1000).toFixed(1).replace(/\.0$/, "") + "K";
  return String(num);
}

function formatDistance(meters) {
  if (meters < 1000) return Math.round(meters) + "m";
  return (meters / 1000).toFixed(1) + "km";
}

function escapeHtml(str) {
  if (!str) return "";
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

function animateCountUp(el, target, duration) {
  duration = duration || 1200;
  const start = 0;
  const startTime = performance.now();
  function update(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = formatNumber(Math.round(start + (target - start) * eased));
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}

/* ================================================================
   SHARED NAVBAR UPDATER
   ================================================================ */
function updateNavbar() {
  const user = Auth && Auth.user;
  const logged = Auth && Auth.isLoggedIn;

  const navLoggedOut = document.getElementById("nav-logged-out");
  const navLoggedIn = document.getElementById("nav-logged-in");
  const navUserName = document.getElementById("nav-user-name");
  const navUserAvatar = document.getElementById("nav-user-avatar");
  const navDashboardLink = document.getElementById("nav-dashboard-link");
  const navReportBtn = document.getElementById("nav-report-btn");

  if (navLoggedOut) navLoggedOut.style.display = logged ? "none" : "flex";
  if (navLoggedIn) navLoggedIn.style.display = logged ? "flex" : "none";
  if (navUserName && user) navUserName.textContent = user.name || "User";
  if (navUserAvatar && user) navUserAvatar.innerHTML = renderUserAvatar(user, 32);
  if (navDashboardLink) {
    navDashboardLink.style.display = (user && (user.role === "authority" || user.role === "admin")) ? "block" : "none";
  }
  if (navReportBtn) navReportBtn.style.display = logged ? "inline-block" : "none";
}
