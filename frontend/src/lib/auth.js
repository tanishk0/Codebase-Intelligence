import { createClient } from "@supabase/supabase-js";
import { setAuthSession, clearAuthSession } from "../api";

let supabaseClient = null;
let initPromise = null;

/**
 * Extracts any OAuth error returned in the URL query string or hash fragment.
 */
export function consumeUrlAuthError() {
  if (typeof window === "undefined") return null;

  const searchParams = new URLSearchParams(window.location.search);
  const hashParams = new URLSearchParams(
    window.location.hash.startsWith("#")
      ? window.location.hash.slice(1)
      : window.location.hash
  );

  const errorDesc =
    searchParams.get("error_description") ||
    hashParams.get("error_description") ||
    searchParams.get("error") ||
    hashParams.get("error");

  if (errorDesc) {
    const cleanUrl = window.location.pathname;
    window.history.replaceState({}, document.title, cleanUrl);
    return decodeURIComponent(errorDesc.replace(/\+/g, " "));
  }
  return null;
}

/**
 * Cleans up OAuth callback parameters from the browser address bar after session exchange.
 */
function scrubOAuthUrlParams() {
  if (typeof window === "undefined") return;
  const hasHashTokens =
    window.location.hash.includes("access_token=") ||
    window.location.hash.includes("error=");
  const searchParams = new URLSearchParams(window.location.search);
  const hasCodeParam = searchParams.has("code");

  if (hasHashTokens || hasCodeParam) {
    searchParams.delete("code");
    const remainingQuery = searchParams.toString();
    const cleanUrl =
      window.location.pathname + (remainingQuery ? `?${remainingQuery}` : "");
    window.history.replaceState({}, document.title, cleanUrl);
  }
}

/**
 * Normalizes a Supabase user object into a clean profile for the UI.
 */
export function normalizeUser(sessionUser) {
  if (!sessionUser) return null;
  const meta = sessionUser.user_metadata || {};
  const appMeta = sessionUser.app_metadata || {};
  const email = sessionUser.email || meta.email || "";
  const fallbackName = email.includes("@") ? email.split("@")[0] : "Operator";

  return {
    id: sessionUser.id,
    email,
    name: meta.full_name || meta.name || meta.user_name || fallbackName,
    avatarUrl: meta.avatar_url || meta.picture || "",
    provider: appMeta.provider || "google",
  };
}

/**
 * Lazily initializes and caches the Supabase Auth client using Vite env vars or `/api/auth/config`.
 */
export async function getSupabaseAuthClient() {
  if (supabaseClient) return supabaseClient;
  if (initPromise) return initPromise;

  initPromise = (async () => {
    let supabaseUrl = import.meta.env?.VITE_SUPABASE_URL || "";
    let supabaseAnonKey = import.meta.env?.VITE_SUPABASE_ANON_KEY || "";

    if (!supabaseUrl || !supabaseAnonKey) {
      try {
        const res = await fetch("/api/auth/config");
        if (res.ok) {
          const cfg = await res.json();
          supabaseUrl = supabaseUrl || cfg.supabase_url || "";
          supabaseAnonKey = supabaseAnonKey || cfg.supabase_anon_key || "";
        }
      } catch {
        // Fallback handled below
      }
    }

    if (!supabaseUrl || !supabaseAnonKey) {
      return null;
    }

    supabaseClient = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
        storageKey: "codebase-copilot-auth",
      },
    });
    return supabaseClient;
  })();

  const client = await initPromise;
  if (!client) {
    initPromise = null;
  }
  return client;
}

/**
 * Bootstraps authentication state and subscribes to session changes.
 */
export async function initializeAuth(onAuthChange) {
  const client = await getSupabaseAuthClient();
  if (!client) {
    clearAuthSession();
    onAuthChange({ user: null, session: null });
    return () => {};
  }

  const {
    data: { session },
  } = await client.auth.getSession();

  if (session?.access_token && session?.user) {
    setAuthSession(session.access_token, session.user.id);
    scrubOAuthUrlParams();
    onAuthChange({
      user: normalizeUser(session.user),
      session,
    });
  } else {
    clearAuthSession();
    onAuthChange({ user: null, session: null });
  }

  const {
    data: { subscription },
  } = client.auth.onAuthStateChange((_event, nextSession) => {
    if (nextSession?.access_token && nextSession?.user) {
      setAuthSession(nextSession.access_token, nextSession.user.id);
      scrubOAuthUrlParams();
      onAuthChange({
        user: normalizeUser(nextSession.user),
        session: nextSession,
      });
    } else {
      clearAuthSession();
      onAuthChange({ user: null, session: null });
    }
  });

  return () => {
    subscription.unsubscribe();
  };
}

/**
 * Initiates the Google OAuth 2.0 flow via Supabase Auth.
 */
export async function signInWithGoogle() {
  const redirectTo = window.location.origin;
  const client = await getSupabaseAuthClient();

  if (client) {
    const { data, error } = await client.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo,
        queryParams: {
          prompt: "select_account",
        },
      },
    });
    if (error) {
      throw new Error(error.message || "Unable to start Google authentication.");
    }
    return data;
  }

  // Fallback to backend OAuth URL generator if client anon key is unavailable
  const res = await fetch(
    `/api/auth/google/url?redirect_to=${encodeURIComponent(redirectTo)}`
  );
  const data = await res.json();
  if (!res.ok || !data.url) {
    throw new Error(
      data.detail || "Google authentication is not configured on the server."
    );
  }
  window.location.assign(data.url);
  return data;
}

/**
 * Signs out the active user session locally and on the backend.
 */
export async function signOutUser() {
  const client = await getSupabaseAuthClient();
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch {
    // Ignore network errors during logout
  }
  if (client) {
    await client.auth.signOut();
  }
  clearAuthSession();
}

