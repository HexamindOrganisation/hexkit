import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AuthProvider } from "./auth/AuthContext";
import { AppRouter } from "./router";

import "./styles.css";


const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // The platform backend's payloads are stable across a single tab
      // session for the queries we cache (agents list, folders, conversations,
      // /me/keys presence). 30s feels right for a chat app — long enough to
      // avoid refetch spam, short enough that other-tab edits surface fast.
      staleTime: 30_000,
      retry: 1,
    },
  },
});


ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
