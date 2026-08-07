/**
 * Smart Community Platform - API Layer
 * Every backend call goes through here. No endpoint URLs elsewhere.
 */

/* ---------- helpers ---------- */
function buildQueryString(params) {
  if (!params || typeof params !== "object") return "";
  const parts = [];
  for (const [key, val] of Object.entries(params)) {
    if (val === null || val === undefined || val === "") continue;
    parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(val));
  }
  return parts.length ? "?" + parts.join("&") : "";
}

function getAccessToken() {
  return localStorage.getItem(CONFIG.ACCESS_TOKEN_KEY);
}
function getRefreshToken() {
  return localStorage.getItem(CONFIG.REFRESH_TOKEN_KEY);
}
function setAccessToken(t) {
  localStorage.setItem(CONFIG.ACCESS_TOKEN_KEY, t);
}
function clearTokens() {
  localStorage.removeItem(CONFIG.ACCESS_TOKEN_KEY);
  localStorage.removeItem(CONFIG.REFRESH_TOKEN_KEY);
  localStorage.removeItem(CONFIG.USER_KEY);
}

/* ---------- base request ---------- */
let _isRefreshing = false;
let _refreshQueue = [];

async function apiRequest(endpoint, options = {}) {
  const url = CONFIG.API_BASE_URL + endpoint;
  const token = getAccessToken();
  const headers = options.headers || {};

  if (token) headers["Authorization"] = "Bearer " + token;
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), CONFIG.API_TIMEOUT_MS);

  try {
    const resp = await fetch(url, {
      method: options.method || "GET",
      headers,
      body: options.body || undefined,
      signal: controller.signal
    });
    clearTimeout(timeout);

    if (resp.status === 401 && !options._retried) {
      return await _handle401(endpoint, options);
    }

    let data;
    const ct = resp.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      data = await resp.json();
    } else {
      data = await resp.text();
    }

    if (!resp.ok) {
      const msg =
        (typeof data === "object" && data !== null ? data.detail || data.message : data) ||
        "Request failed";
      const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
      err.status = resp.status;
      err.data = data;
      throw err;
    }
    return data;
  } catch (err) {
    clearTimeout(timeout);
    if (err.name === "AbortError") {
      throw new Error("Request timed out. Please try again.");
    }
    if (!err.status) {
      throw new Error("Network error. Please check your connection.");
    }
    throw err;
  }
}

async function _handle401(endpoint, options) {
  if (_isRefreshing) {
    return new Promise((resolve, reject) => {
      _refreshQueue.push({ resolve, reject, endpoint, options });
    });
  }
  _isRefreshing = true;
  try {
    const rt = getRefreshToken();
    if (!rt) throw new Error("No refresh token");
    const data = await fetch(CONFIG.API_BASE_URL + "/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt })
    }).then((r) => {
      if (!r.ok) throw new Error("Refresh failed");
      return r.json();
    });
    setAccessToken(data.access_token);
    _isRefreshing = false;
    _refreshQueue.forEach((q) => {
      apiRequest(q.endpoint, { ...q.options, _retried: true }).then(q.resolve, q.reject);
    });
    _refreshQueue = [];
    return apiRequest(endpoint, { ...options, _retried: true });
  } catch (_) {
    _isRefreshing = false;
    _refreshQueue.forEach((q) => q.reject(new Error("Session expired")));
    _refreshQueue = [];
    clearTokens();
    if (!window.location.pathname.endsWith("auth.html")) {
      window.location.href = "auth.html?redirect=" + encodeURIComponent(window.location.href);
    }
    throw new Error("Session expired. Please log in again.");
  }
}

/* ================================================================
   AUTH API
   ================================================================ */
const AuthAPI = {
  register(data) {
    return apiRequest("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(data)
    });
  },

  login(email, password, rememberMe) {
    return apiRequest("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, remember_me: rememberMe || false })
    });
  },

  logout() {
    return apiRequest("/api/auth/logout", { method: "POST" });
  },

  getMe() {
    return apiRequest("/api/auth/me");
  },

  refreshToken(refreshToken) {
    return apiRequest("/api/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken })
    });
  },

  verifyEmail(token) {
    return apiRequest("/api/auth/verify-email/" + token);
  },

  forgotPassword(email) {
    return apiRequest("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email })
    });
  },

  resetPassword(token, newPassword, confirmPassword) {
    return apiRequest("/api/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password: newPassword, confirm_password: confirmPassword })
    });
  },

  changePassword(currentPassword, newPassword, confirmPassword) {
    return apiRequest("/api/auth/change-password", {
      method: "PUT",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword
      })
    });
  },

  updateProfile(data) {
    return apiRequest("/api/auth/update-profile", {
      method: "PUT",
      body: JSON.stringify(data)
    });
  },

  deleteAccount(password, reason) {
    return apiRequest("/api/auth/delete-account", {
      method: "DELETE",
      body: JSON.stringify({ password, reason })
    });
  }
};

/* ================================================================
   ISSUES API
   ================================================================ */
const IssuesAPI = {
  create(data) {
    return apiRequest("/api/issues/", {
      method: "POST",
      body: JSON.stringify(data)
    });
  },

  uploadImage(file) {
    const fd = new FormData();
    fd.append("file", file);
    return apiRequest("/api/issues/upload", {
      method: "POST",
      body: fd,
      headers: {}
    });
  },

  addImage(uuid, file) {
    const fd = new FormData();
    fd.append("file", file);
    return apiRequest("/api/issues/" + uuid + "/images", {
      method: "POST",
      body: fd,
      headers: {}
    });
  },

  checkDuplicates(payload) {
    return apiRequest("/api/issues/duplicate-check", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  getList(filters) {
    return apiRequest("/api/issues/" + buildQueryString(filters));
  },

  getMapMarkers(filters) {
    return apiRequest("/api/issues/map" + buildQueryString(filters));
  },

  getStats(city, days) {
    return apiRequest("/api/issues/stats" + buildQueryString({ city, days }));
  },

  getNearby(lat, lng, radiusKm, filters) {
    return apiRequest(
      "/api/issues/nearby" + buildQueryString({ lat, lng, radius_km: radiusKm, ...filters })
    );
  },

  getDetail(uuid) {
    return apiRequest("/api/issues/" + uuid);
  },

  update(uuid, data) {
    return apiRequest("/api/issues/" + uuid, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  },

  delete(uuid) {
    return apiRequest("/api/issues/" + uuid, { method: "DELETE" });
  },

  updateStatus(uuid, data) {
    return apiRequest("/api/issues/" + uuid + "/status", {
      method: "PATCH",
      body: JSON.stringify(data)
    });
  },

  updatePriority(uuid, data) {
    return apiRequest("/api/issues/" + uuid + "/priority", {
      method: "PATCH",
      body: JSON.stringify(data)
    });
  },

  vote(uuid, voteType) {
    return apiRequest("/api/issues/" + uuid + "/vote", {
      method: "POST",
      body: JSON.stringify({ vote_type: voteType || "upvote" })
    });
  },

  addComment(uuid, data) {
    return apiRequest("/api/issues/" + uuid + "/comments", {
      method: "POST",
      body: JSON.stringify(data)
    });
  },

  deleteComment(issueUuid, commentUuid) {
    return apiRequest("/api/issues/" + issueUuid + "/comments/" + commentUuid, {
      method: "DELETE"
    });
  },

  confirmResolution(uuid, data) {
    return apiRequest("/api/issues/" + uuid + "/confirm", {
      method: "POST",
      body: JSON.stringify(data)
    });
  },

  submitResolution(uuid, data) {
    return apiRequest("/api/issues/" + uuid + "/resolution", {
      method: "PATCH",
      body: JSON.stringify(data)
    });
  },

  getMyIssues(filters) {
    return apiRequest("/api/issues/" + buildQueryString({ ...filters, my_issues: true }));
  },

  getAssignedToMe(filters) {
    return apiRequest("/api/issues/" + buildQueryString({ ...filters, assigned_to_me: true }));
  }
};

/* ================================================================
   USERS API
   ================================================================ */
const UsersAPI = {
  getProfile(uuid) {
    return apiRequest("/api/users/" + uuid);
  },

  getList(filters) {
    return apiRequest("/api/users/" + buildQueryString(filters));
  },

  banUser(uuid, isActive, reason) {
    return apiRequest("/api/users/" + uuid + "/ban", {
      method: "PUT",
      body: JSON.stringify({ is_active: isActive, reason })
    });
  },

  changeRole(uuid, role) {
    return apiRequest("/api/users/" + uuid + "/role", {
      method: "PUT",
      body: JSON.stringify({ role })
    });
  },

  getUserIssues(uuid, filters) {
    return apiRequest("/api/users/" + uuid + "/issues" + buildQueryString(filters));
  },

  getLeaderboard(limit) {
    return apiRequest("/api/users/leaderboard" + buildQueryString({ limit }));
  }
};
