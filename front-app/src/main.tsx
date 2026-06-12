import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AuthProvider } from "./auth/AuthContext";
import { AppRouter } from "./router";

// HexaUI fonts: Hanken Grotesk (UI), Source Serif 4 (display), IBM Plex Mono
// (data). Loaded here so the whole app — chrome + AgentUI widgets — picks them
// up via the --font-* tokens in agent-ui/shadcn.css.
import "@fontsource/hanken-grotesk/400.css";
import "@fontsource/hanken-grotesk/500.css";
import "@fontsource/hanken-grotesk/600.css";
import "@fontsource/source-serif-4/400.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";

// KaTeX styles + fonts — required for the markdown renderer's math typesetting
// (\( … \), \[ … \], $$ … $$) to display correctly.
import "katex/dist/katex.min.css";

import "./styles.css";


const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
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
