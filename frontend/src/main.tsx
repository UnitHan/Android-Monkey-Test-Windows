import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ApiError } from "./api/client";
import { App } from "./App";
import { installReloadGuard } from "./reloadGuard";
import "./styles.css";
import "./scrollShadows.css";

const removeReloadGuard = installReloadGuard();
if (import.meta.hot) import.meta.hot.dispose(removeReloadGuard);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // backend not up yet (network error / proxy 5xx without problem body): keep retrying; 4xx never; others twice
      retry: (count, err) =>
        err instanceof ApiError && (err.code === "network_error" || err.code.startsWith("http_5")) ? count < 60
          : !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
      retryDelay: (count) => Math.min(500 * 2 ** count, 4000),
      refetchOnWindowFocus: false,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
