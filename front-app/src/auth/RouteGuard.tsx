import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext";


/**
 * Wraps private routes. Redirects to /login when no token. While the auth
 * provider is still revalidating the stored token, renders a small skeleton
 * so a hard refresh on a private route doesn't flash the login screen.
 */
export function RouteGuard({ children }: { children: ReactNode }) {
  const { token, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }

  if (!token) {
    // Preserve where the user was headed so login can return them to it.
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <>{children}</>;
}
