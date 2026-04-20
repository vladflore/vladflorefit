import { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } from "./supabase-config.js";

const STORAGE_KEY = "flexary_auth_session";

const config = {
  signInEnabled: false,
};

const state = {
  session: null,
  user: null,
  lastError: "",
};

function normalizeConfig(raw) {
  const source = raw && typeof raw === "object" ? raw : {};
  return {
    signInEnabled: source.enableSignIn !== false,
  };
}

async function tryLoadJson(url) {
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

async function loadConfig() {
  return normalizeConfig(
    await tryLoadJson(`${SUPABASE_URL}/functions/v1/config`),
  );
}

function applyConfig(nextConfig) {
  config.signInEnabled = nextConfig.signInEnabled;
  // config.signInEnabled = true;
}

function cloneAuthState() {
  return {
    session: state.session ? { ...state.session } : null,
    user: state.user ? { ...state.user } : null,
    lastError: state.lastError,
  };
}

function emitAuthChange() {
  window.dispatchEvent(
    new CustomEvent("flexary-auth-change", {
      detail: cloneAuthState(),
    }),
  );
}

function saveSession(session) {
  state.session = session || null;
  if (state.session) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.session));
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function clearSession() {
  state.user = null;
  saveSession(null);
}

function loadSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

function authHeaders(token) {
  const headers = {
    apikey: SUPABASE_PUBLISHABLE_KEY,
    "Content-Type": "application/json",
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function authRequest(path, options = {}) {
  const { method = "GET", body, token } = options;
  const response = await fetch(`${SUPABASE_URL}/auth/v1${path}`, {
    method,
    headers: authHeaders(token),
    body: body ? JSON.stringify(body) : undefined,
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const message =
      payload?.msg ||
      payload?.error_description ||
      payload?.error ||
      `Auth request failed with status ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

function sessionExpired(session) {
  if (!session?.expires_at) return false;
  const expiresAtMs = Number(session.expires_at) * 1000;
  return Number.isFinite(expiresAtMs) && Date.now() > expiresAtMs - 30_000;
}

async function refreshSessionIfNeeded() {
  if (!state.session?.refresh_token) return null;
  if (!sessionExpired(state.session)) return state.session;

  const payload = await authRequest("/token?grant_type=refresh_token", {
    method: "POST",
    body: {
      refresh_token: state.session.refresh_token,
    },
  });

  const refreshed = payload?.access_token
    ? {
        ...payload,
        refresh_token: payload.refresh_token || state.session.refresh_token,
      }
    : null;
  saveSession(refreshed);
  return state.session;
}

async function getUserFromToken(token) {
  const payload = await authRequest("/user", { token });
  state.user = payload || null;
  return state.user;
}

async function syncUserFromSession() {
  if (!state.session?.access_token) {
    state.user = null;
    emitAuthChange();
    return null;
  }

  try {
    await refreshSessionIfNeeded();
    const user = await getUserFromToken(state.session.access_token);
    state.lastError = "";
    emitAuthChange();
    return user;
  } catch (error) {
    state.lastError = error instanceof Error ? error.message : String(error);
    // Only clear the session on explicit auth errors (HTTP responses), not on
    // network-level failures (TypeError) which can happen on quick page refreshes.
    if (!(error instanceof TypeError)) {
      clearSession();
    }
    emitAuthChange();
    return null;
  }
}

async function init() {
  applyConfig(await loadConfig());

  if (window.location.hash?.includes("access_token")) {
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const fragmentSession = {
      access_token: params.get("access_token"),
      refresh_token: params.get("refresh_token"),
      expires_at: params.get("expires_at"),
      token_type: params.get("token_type"),
    };
    if (fragmentSession.access_token) {
      saveSession(fragmentSession);
      window.history.replaceState(
        {},
        "",
        window.location.pathname + window.location.search,
      );
    }
  }

  state.session = loadSession();
  await syncUserFromSession();
  return cloneAuthState();
}

async function ensureReady() {
  await window.flexaryAuth.ready;
}

async function signUp(email, password) {
  await ensureReady();
  const payload = await authRequest("/signup", {
    method: "POST",
    body: {
      email,
      password,
      email_redirect_to: "https://vladflore.fit/flexary/index.html",
    },
  });

  saveSession(payload?.session || null);
  state.user = payload?.user || null;
  state.lastError = "";
  if (state.session?.access_token && !state.user) {
    await getUserFromToken(state.session.access_token);
  }
  emitAuthChange();
  return {
    user: state.user,
    session: state.session,
  };
}

async function signIn(email, password) {
  await ensureReady();
  const payload = await authRequest("/token?grant_type=password", {
    method: "POST",
    body: {
      email,
      password,
    },
  });

  saveSession(payload || null);
  state.lastError = "";
  await getUserFromToken(state.session?.access_token);
  emitAuthChange();
  return {
    user: state.user,
    session: state.session,
  };
}

async function signInWithMagicLink(email) {
  await ensureReady();
  const payload = await authRequest("/otp", {
    method: "POST",
    body: {
      email,
      create_user: true,
      email_redirect_to: "https://vladflore.fit/flexary/index.html",
    },
  });
  state.lastError = "";
  emitAuthChange();
  return payload;
}

async function signOut() {
  await ensureReady();
  if (state.session?.access_token) {
    try {
      await authRequest("/logout", {
        method: "POST",
        token: state.session.access_token,
      });
    } catch {
      // Clear local session even if remote logout fails.
    }
  }

  state.lastError = "";
  clearSession();
  emitAuthChange();
}

async function getCurrentUser() {
  await ensureReady();
  await refreshSessionIfNeeded();
  if (!state.user && state.session?.access_token) {
    await getUserFromToken(state.session.access_token);
  }
  return state.user;
}

async function getAccessToken() {
  await ensureReady();
  await refreshSessionIfNeeded();
  return state.session?.access_token || null;
}

window.flexaryAuth = {
  ready: Promise.resolve().then(init),
  state,
  isSignInEnabled() {
    return config.signInEnabled;
  },
  getCurrentUser,
  signUp,
  signIn,
  signInWithMagicLink,
  signOut,
  getAccessToken,
};
