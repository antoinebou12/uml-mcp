import * as React from "react";
import { ApiError, get, getToken } from "./api";
import type { Overview } from "./types";

interface Session {
  overview?: Overview;
  mode: "local" | "enterprise" | "unknown";
  authError?: ApiError;
  signedIn: boolean;
  stopped: boolean;
  setStopped: (v: boolean) => void;
  refresh: () => void;
}

const SessionContext = React.createContext<Session>({
  mode: "unknown",
  signedIn: false,
  stopped: false,
  setStopped: () => {},
  refresh: () => {},
});

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [overview, setOverview] = React.useState<Overview>();
  const [authError, setAuthError] = React.useState<ApiError>();
  const [stopped, setStopped] = React.useState(false);
  const [tick, setTick] = React.useState(0);
  const refresh = React.useCallback(() => setTick((t) => t + 1), []);

  React.useEffect(() => {
    get<Overview>("/admin/api/overview")
      .then((o) => {
        setOverview(o);
        setAuthError(undefined);
      })
      .catch((e) => setAuthError(e instanceof ApiError ? e : new ApiError(0, String(e), null)));
  }, [tick]);

  const mode = overview ? (overview.local ? "local" : "enterprise") : "unknown";
  const value: Session = {
    overview,
    mode,
    authError,
    signedIn: mode === "local" ? Boolean(getToken()) : Boolean(overview),
    stopped,
    setStopped,
    refresh,
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export const useSession = () => React.useContext(SessionContext);
