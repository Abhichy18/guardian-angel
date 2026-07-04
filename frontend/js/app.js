/*
 * Guardian Angel — Common Frontend Utilities
 *
 * Manages authentication state, local storage keys, network API calls,
 * and routing helper functions across all application views.
 */

const API_BASE = "http://127.0.0.1:8000/api";

const StorageKeys = {
  TOKEN: "ga_token",
  USER: "ga_user"
};

/**
 * Perform a request to the backend API, automatically appending JWT auth headers.
 */
async function apiRequest(endpoint, options = {}) {
  const token = localStorage.getItem(StorageKeys.TOKEN);
  
  const headers = {
    "Content-Type": "application/json",
    ...options.headers
  };
  
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  
  const fetchOptions = {
    ...options,
    headers
  };
  
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, fetchOptions);
    
    // Check if unauthorized, trigger auto-logout
    if (response.status === 401 && endpoint !== "/auth/login") {
      logout();
      return null;
    }
    
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "API Request failed");
    }
    return data;
  } catch (error) {
    console.error(`API Error on ${endpoint}:`, error);
    throw error;
  }
}

/**
 * Handle user login and store credentials.
 */
function saveSession(token, user) {
  localStorage.setItem(StorageKeys.TOKEN, token);
  localStorage.setItem(StorageKeys.USER, JSON.stringify(user));
}

/**
 * Clear user session and redirect to landing page.
 */
function logout() {
  localStorage.removeItem(StorageKeys.TOKEN);
  localStorage.removeItem(StorageKeys.USER);
  window.location.href = "/";
}

/**
 * Retrieve current logged-in user profile from storage.
 */
function getCurrentUser() {
  const userJson = localStorage.getItem(StorageKeys.USER);
  if (!userJson) return null;
  try {
    return JSON.parse(userJson);
  } catch (e) {
    return null;
  }
}

/**
 * Enforce that the user is logged in. Returns user if successful, redirects otherwise.
 */
function requireAuth(expectedRole = null) {
  const user = getCurrentUser();
  if (!user) {
    window.location.href = "/";
    return null;
  }
  
  if (expectedRole && user.role !== expectedRole) {
    if (user.role === "elder") {
      window.location.href = "/elder-dashboard";
    } else {
      window.location.href = "/family-dashboard";
    }
    return null;
  }
  
  return user;
}

/**
 * Redirect active sessions automatically from login screen.
 */
function redirectIfLoggedIn() {
  const user = getCurrentUser();
  if (user) {
    if (user.role === "elder") {
      window.location.href = "/elder-dashboard";
    } else {
      window.location.href = "/family-dashboard";
    }
  }
}
