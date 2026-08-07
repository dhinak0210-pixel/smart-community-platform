/**
 * Smart Community Platform - Global Configuration
 * All constants, API settings, and design tokens.
 * Imported by every other JS file.
 */

const CONFIG = {
  API_BASE_URL: (typeof window !== "undefined" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") 
    ? window.location.origin 
    : "http://localhost:8001",
  API_PREFIX: "/api",

  ACCESS_TOKEN_KEY: "sc_access_token",
  REFRESH_TOKEN_KEY: "sc_refresh_token",
  USER_KEY: "sc_user",

  MAP_DEFAULT_LAT: 24.7136,
  MAP_DEFAULT_LNG: 46.6753,
  MAP_DEFAULT_ZOOM: 12,
  MAP_MAX_MARKERS: 500,

  DEFAULT_PAGE_SIZE: 20,
  MAX_PAGE_SIZE: 100,

  MAX_IMAGE_SIZE_MB: 5,
  ALLOWED_IMAGE_TYPES: ["image/jpeg", "image/png", "image/webp"],

  API_TIMEOUT_MS: 10000,
  TOAST_DURATION_MS: 4000,
  MAP_REFRESH_INTERVAL_MS: 30000,

  STATUS_LABELS: {
    reported: "Reported",
    under_review: "Under Review",
    acknowledged: "Acknowledged",
    assigned: "Assigned",
    in_progress: "In Progress",
    pending_citizen: "Awaiting Confirmation",
    resolved: "Resolved",
    rejected: "Rejected",
    duplicate: "Duplicate"
  },

  STATUS_COLORS: {
    reported: "#DC2626",
    under_review: "#7C3AED",
    acknowledged: "#D97706",
    assigned: "#2563EB",
    in_progress: "#0891B2",
    pending_citizen: "#EA580C",
    resolved: "#16A34A",
    rejected: "#6B7280",
    duplicate: "#9CA3AF"
  },

  PRIORITY_LABELS: {
    critical: "Critical",
    high: "High",
    medium: "Medium",
    low: "Low"
  },

  PRIORITY_COLORS: {
    critical: "#DC2626",
    high: "#EA580C",
    medium: "#D97706",
    low: "#6B7280"
  },

  CATEGORY_LABELS: {
    infrastructure: "Infrastructure",
    waste: "Waste Management",
    safety: "Public Safety",
    environment: "Environment",
    utilities: "Utilities",
    traffic: "Traffic",
    noise: "Noise",
    flooding: "Flooding",
    other: "Other"
  },

  CATEGORY_ICONS: {
    infrastructure: "bi-building",
    waste: "bi-trash",
    safety: "bi-shield-exclamation",
    environment: "bi-tree",
    utilities: "bi-lightning",
    traffic: "bi-car-front",
    noise: "bi-volume-up",
    flooding: "bi-water",
    other: "bi-question-circle"
  }
};

Object.freeze(CONFIG);
Object.freeze(CONFIG.STATUS_LABELS);
Object.freeze(CONFIG.STATUS_COLORS);
Object.freeze(CONFIG.PRIORITY_LABELS);
Object.freeze(CONFIG.PRIORITY_COLORS);
Object.freeze(CONFIG.CATEGORY_LABELS);
Object.freeze(CONFIG.CATEGORY_ICONS);
Object.freeze(CONFIG.ALLOWED_IMAGE_TYPES);
