import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { RouteGuard } from "./auth/RouteGuard";
import { AppShell } from "./layout/AppShell";
import { ChatPage } from "./pages/ChatPage";
import { LoginPage } from "./pages/LoginPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SignupPage } from "./pages/SignupPage";


/**
 * Public routes (login/signup) sit outside the shell so an unauthenticated
 * user never sees the empty sidebar flicker. Everything else lives inside
 * RouteGuard → AppShell.
 */
export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  {
    path: "/",
    element: (
      <RouteGuard>
        <AppShell />
      </RouteGuard>
    ),
    children: [
      { index: true, element: <ChatPage /> },
      { path: "c/:id", element: <ChatPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
]);


export function AppRouter() {
  return <RouterProvider router={router} />;
}
