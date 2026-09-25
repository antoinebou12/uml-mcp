import * as React from "react";
import { ApiError, get } from "./api";

export interface Query<T> {
  data: T | undefined;
  error: ApiError | Error | undefined;
  loading: boolean;
  reload: () => void;
}

/** Fetch JSON, optionally polling every `intervalMs` while the tab is visible. */
export function useApi<T>(path: string | null, intervalMs?: number): Query<T> {
  const [data, setData] = React.useState<T>();
  const [error, setError] = React.useState<ApiError | Error>();
  const [loading, setLoading] = React.useState(Boolean(path));
  const [tick, setTick] = React.useState(0);
  const reload = React.useCallback(() => setTick((t) => t + 1), []);

  React.useEffect(() => {
    if (!path) return;
    let alive = true;
    const run = () => {
      if (document.visibilityState === "hidden") return;
      get<T>(path)
        .then((d) => {
          if (!alive) return;
          setData(d);
          setError(undefined);
        })
        .catch((e: Error) => alive && setError(e))
        .finally(() => alive && setLoading(false));
    };
    run();
    const id = intervalMs ? window.setInterval(run, intervalMs) : undefined;
    return () => {
      alive = false;
      if (id) window.clearInterval(id);
    };
  }, [path, intervalMs, tick]);

  return { data, error, loading, reload };
}
