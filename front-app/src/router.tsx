import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppShell } from "./layout/AppShell";
import { ChatPage } from "./pages/ChatPage";
import { FilesPage } from "./pages/FilesPage";
import { SettingsPage } from "./pages/SettingsPage";

/**
 * Single-user: no login/signup, no route guard. Everything lives inside the
 * HexaUI chrome shell. `/` is the greeting (no conversation yet); `/c/:id`
 * loads a conversation.
 */
export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <ChatPage /> },
      { path: "c/:id", element: <ChatPage /> },
      { path: "files", element: <FilesPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
