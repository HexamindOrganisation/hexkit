/**
 * Auth state for the app.
 *
 * Owns the JWT + the current user record. Mounts try to revalidate a stored
 * token via GET /me; if that fails the token is cleared. Once `loading` is
 * false, callers know auth state is settled.
 */

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import {
  clearToken,
  getToken,
  HttpError,
  setToken,
} from "../api/client";
import { Credentials, getMe, login as apiLogin, signup as apiSignup, UserOut } from "../api/auth";


interface AuthState {
  token: string | null;
  user: UserOut | null;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (creds: Credentials) => Promise<void>;
  signup: (creds: Credentials) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);


export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: getToken(),
    user: null,
    loading: !!getToken(),  // only "loading" if we have a token to validate
  });

  // On mount: if a token exists, revalidate it. If it's stale, clear.
  useEffect(() => {
    if (!state.token) {
      setState((s) => ({ ...s, loading: false }));
      return;
    }
    let cancelled = false;
    getMe()
      .then((user) => {
        if (!cancelled) setState({ token: state.token, user, loading: false });
      })
      .catch((err) => {
        if (cancelled) return;
        // 401 already cleared the token in the client; just reset state.
        if (err instanceof HttpError && err.status === 401) {
          setState({ token: null, user: null, loading: false });
        } else {
          // Network failure shouldn't log the user out — try again on the
          // next request and let them see the cached header for now.
          setState((s) => ({ ...s, loading: false }));
        }
      });
    return () => {
      cancelled = true;
    };
    // Only run on first mount; subsequent token changes go through login/signup
    // which set both token + user atomically.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (creds: Credentials) => {
    const result = await apiLogin(creds);
    setToken(result.access_token);
    setState({ token: result.access_token, user: result.user, loading: false });
  }, []);

  const signup = useCallback(async (creds: Credentials) => {
    const result = await apiSignup(creds);
    setToken(result.access_token);
    setState({ token: result.access_token, user: result.user, loading: false });
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setState({ token: null, user: null, loading: false });
    // Hard-nav so any in-flight queries from the protected app tree are
    // discarded along with React state.
    window.location.assign("/login");
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}


export function useAuth(): AuthContextValue {
  const v = useContext(AuthContext);
  if (v === null) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return v;
}
