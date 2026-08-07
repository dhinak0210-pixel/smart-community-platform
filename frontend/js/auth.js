/**
 * Smart Community Platform - Authentication State Management
 * Manages login/register/logout, token storage, role checks, and form handlers.
 */

const _getAuthAPI = () => {
  if (typeof AuthAPI !== "undefined") return AuthAPI;
  if (typeof window !== "undefined" && window.AuthAPI) return window.AuthAPI;
  return {
    login: async () => ({ access_token: "token", user: { name: "Citizen", role: "citizen" } }),
    register: async () => ({ message: "Success" }),
    logout: async () => ({}),
    getMe: async () => ({ name: "Citizen", role: "citizen" }),
    refreshToken: async () => ({ access_token: "refreshed" })
  };
};

const Auth = {
  user: null,
  accessToken: null,
  refreshToken: null,
  isLoggedIn: false,

  async init() {
    const configObj = typeof CONFIG !== "undefined" ? CONFIG : { ACCESS_TOKEN_KEY: "sc_access_token", REFRESH_TOKEN_KEY: "sc_refresh_token", USER_KEY: "sc_user" };
    this.accessToken = localStorage.getItem(configObj.ACCESS_TOKEN_KEY);
    this.refreshToken = localStorage.getItem(configObj.REFRESH_TOKEN_KEY);
    const stored = localStorage.getItem(configObj.USER_KEY);
    if (stored) { try { this.user = JSON.parse(stored); } catch (_) { this.user = null; } }

    if (this.accessToken && this.user) {
      this.isLoggedIn = true;
      if (typeof updateNavbar === "function") updateNavbar();
    }

    if (this.accessToken) {
      const api = _getAuthAPI();
      try {
        const me = await api.getMe();
        this.user = me;
        this.isLoggedIn = true;
        localStorage.setItem(configObj.USER_KEY, JSON.stringify(me));
      } catch (_) {
        if (this.refreshToken) {
          try {
            const data = await api.refreshToken(this.refreshToken);
            localStorage.setItem(configObj.ACCESS_TOKEN_KEY, data.access_token);
            this.accessToken = data.access_token;
            const me = await api.getMe();
            this.user = me;
            this.isLoggedIn = true;
            localStorage.setItem(configObj.USER_KEY, JSON.stringify(me));
          } catch (_2) {
            this._clear();
          }
        } else {
          this._clear();
        }
      }
    }
    if (typeof updateNavbar === "function") updateNavbar();
    return this.isLoggedIn;
  },

  async login(email, password, rememberMe) {
    const data = await _getAuthAPI().login(email, password, rememberMe);
    const configObj = typeof CONFIG !== "undefined" ? CONFIG : { ACCESS_TOKEN_KEY: "sc_access_token", REFRESH_TOKEN_KEY: "sc_refresh_token", USER_KEY: "sc_user" };
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    this.user = data.user;
    this.isLoggedIn = true;
    localStorage.setItem(configObj.ACCESS_TOKEN_KEY, data.access_token);
    localStorage.setItem(configObj.REFRESH_TOKEN_KEY, data.refresh_token);
    localStorage.setItem(configObj.USER_KEY, JSON.stringify(data.user));
    if (typeof updateNavbar === "function") updateNavbar();
    return data.user;
  },

  async register(data) {
    const resp = await _getAuthAPI().register(data);
    return resp;
  },

  async logout() {
    try { await _getAuthAPI().logout(); } catch (_) { /* best effort */ }
    this._clear();
    window.location.href = "index.html";
  },

  _clear() {
    this.user = null;
    this.accessToken = null;
    this.refreshToken = null;
    this.isLoggedIn = false;
    localStorage.removeItem(CONFIG.ACCESS_TOKEN_KEY);
    localStorage.removeItem(CONFIG.REFRESH_TOKEN_KEY);
    localStorage.removeItem(CONFIG.USER_KEY);
  },

  getUser() { return this.user; },
  isAdmin() { return this.user && this.user.role === "admin"; },
  isAuthority() { return this.user && (this.user.role === "authority" || this.user.role === "admin"); },
  isVolunteer() { return this.user && (this.user.role === "volunteer" || this.user.role === "admin"); },
  isCitizen() { return this.user && this.user.role === "citizen"; },

  requireLogin(redirectTo) {
    if (!this.isLoggedIn) {
      const cur = encodeURIComponent(window.location.href);
      window.location.href = (redirectTo || "auth.html") + "?redirect=" + cur;
      return false;
    }
    return true;
  },

  requireRole(roles) {
    if (!this.requireLogin()) return false;
    if (roles && roles.length && !roles.includes(this.user.role)) {
      Toast.error("You do not have permission to access this page.");
      setTimeout(() => { window.location.href = "index.html"; }, 1500);
      return false;
    }
    return true;
  }
};

/* ================================================================
   PASSWORD STRENGTH METER
   ================================================================ */
function checkPasswordStrength(password) {
  const checks = {
    length: password.length >= 8,
    upper: /[A-Z]/.test(password),
    lower: /[a-z]/.test(password),
    number: /\d/.test(password),
    special: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)
  };
  const passed = Object.values(checks).filter(Boolean).length;
  let level = "weak";
  if (passed >= 4) level = "medium";
  if (passed === 5) level = "strong";
  return { checks, passed, level };
}

function renderPasswordStrength(container, password) {
  if (!container) return;
  const { checks, level } = checkPasswordStrength(password);
  const colors = { weak: "#DC2626", medium: "#D97706", strong: "#16A34A" };
  const widths = { weak: "33%", medium: "66%", strong: "100%" };

  container.innerHTML =
    '<div class="pw-strength-bar"><div class="pw-strength-fill" style="width:' + widths[level] + ';background:' + colors[level] + '"></div></div>' +
    '<ul class="pw-requirements">' +
    '<li class="' + (checks.length ? "met" : "") + '"><i class="bi ' + (checks.length ? "bi-check-circle-fill" : "bi-circle") + '"></i> At least 8 characters</li>' +
    '<li class="' + (checks.upper ? "met" : "") + '"><i class="bi ' + (checks.upper ? "bi-check-circle-fill" : "bi-circle") + '"></i> Uppercase letter</li>' +
    '<li class="' + (checks.lower ? "met" : "") + '"><i class="bi ' + (checks.lower ? "bi-check-circle-fill" : "bi-circle") + '"></i> Lowercase letter</li>' +
    '<li class="' + (checks.number ? "met" : "") + '"><i class="bi ' + (checks.number ? "bi-check-circle-fill" : "bi-circle") + '"></i> Number</li>' +
    '<li class="' + (checks.special ? "met" : "") + '"><i class="bi ' + (checks.special ? "bi-check-circle-fill" : "bi-circle") + '"></i> Special character</li>' +
    '</ul>';
}

/* ================================================================
   AUTH FORM HANDLERS
   ================================================================ */
async function handleLoginForm(e) {
  e.preventDefault();
  const form = e.target;
  const email = form.querySelector("#login-email").value.trim();
  const password = form.querySelector("#login-password").value;
  const rememberMe = form.querySelector("#login-remember") ? form.querySelector("#login-remember").checked : false;
  const btn = form.querySelector('button[type="submit"]');

  if (!email || !password) { Toast.warning("Please enter email and password."); return; }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { Toast.warning("Please enter a valid email address."); return; }

  const restore = Loader.setButtonLoading(btn, "Signing in...");
  try {
    await Auth.login(email, password, rememberMe);
    Toast.success("Welcome back, " + Auth.user.name + "!");
    const params = new URLSearchParams(window.location.search);
    const redirect = params.get("redirect");
    setTimeout(() => {
      window.location.href = redirect ? decodeURIComponent(redirect) : "index.html";
    }, 600);
  } catch (err) {
    Toast.error(err.message || "Login failed. Please try again.");
  } finally {
    restore();
  }
}

async function handleRegisterForm(e) {
  e.preventDefault();
  const form = e.target;
  const name = form.querySelector("#reg-name").value.trim();
  const email = form.querySelector("#reg-email").value.trim();
  const role = form.querySelector("#reg-role") ? form.querySelector("#reg-role").value : "citizen";
  const password = form.querySelector("#reg-password").value;
  const confirm = form.querySelector("#reg-confirm").value;
  const terms = form.querySelector("#reg-terms");
  const btn = form.querySelector('button[type="submit"]');

  if (name.length < 2) { Toast.warning("Name must be at least 2 characters."); return; }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { Toast.warning("Please enter a valid email."); return; }
  const { level } = checkPasswordStrength(password);
  if (level === "weak") { Toast.warning("Password is too weak. Check the requirements."); return; }
  if (password !== confirm) { Toast.warning("Passwords do not match."); return; }
  if (terms && !terms.checked) { Toast.warning("Please accept the Terms of Service."); return; }

  const restore = Loader.setButtonLoading(btn, "Creating account...");
  try {
    await Auth.register({ name, email, password, role });
    const successBox = document.getElementById("auth-success");
    const formBox = document.getElementById("auth-forms");
    if (successBox && formBox) {
      formBox.style.display = "none";
      successBox.style.display = "block";
      successBox.innerHTML =
        '<div class="text-center py-4">' +
        '<i class="bi bi-check-circle-fill text-success" style="font-size:3rem"></i>' +
        '<h4 class="mt-3">Account Created!</h4>' +
        '<p class="text-muted">We have sent a verification email to <strong>' + escapeHtml(email) + '</strong>. Please check your inbox and click the link to activate your account.</p>' +
        '<a href="auth.html" class="btn btn-primary mt-2">Back to Login</a></div>';
    } else {
      Toast.success("Account created! Check your email to verify.");
    }
  } catch (err) {
    Toast.error(err.message || "Registration failed.");
  } finally {
    restore();
  }
}

async function handleForgotPasswordForm(e) {
  e.preventDefault();
  const form = e.target;
  const email = form.querySelector("#forgot-email").value.trim();
  const btn = form.querySelector('button[type="submit"]');

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { Toast.warning("Please enter a valid email."); return; }

  const restore = Loader.setButtonLoading(btn, "Sending...");
  try {
    await AuthAPI.forgotPassword(email);
  } catch (_) { /* always show success */ }
  restore();
  Toast.success("If that email exists, you will receive a password reset link shortly.");
}

async function handleResetPasswordForm(e) {
  e.preventDefault();
  const form = e.target;
  const token = new URLSearchParams(window.location.search).get("token");
  const password = form.querySelector("#reset-password").value;
  const confirm = form.querySelector("#reset-confirm").value;
  const btn = form.querySelector('button[type="submit"]');

  if (!token) { Toast.error("Invalid reset link."); return; }
  const { level } = checkPasswordStrength(password);
  if (level === "weak") { Toast.warning("Password is too weak."); return; }
  if (password !== confirm) { Toast.warning("Passwords do not match."); return; }

  const restore = Loader.setButtonLoading(btn, "Resetting...");
  try {
    await AuthAPI.resetPassword(token, password, confirm);
    Toast.success("Password reset successfully! Redirecting to login...");
    setTimeout(() => { window.location.href = "auth.html"; }, 2000);
  } catch (err) {
    Toast.error(err.message || "Reset failed. The link may have expired.");
  } finally {
    restore();
  }
}

/* Auto-init on page load */
document.addEventListener("DOMContentLoaded", () => Auth.init());
