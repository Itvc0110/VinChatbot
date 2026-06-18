"use client";

import { useCallback, useEffect, useState } from "react";
import type { AsyncState } from "./portalTypes";

// Minimal data-fetching hook giving every API-backed view a uniform loading / error /
// success lifecycle (the empty state is decided by the view from the resolved data).
// `reload` lets actions refetch after a mutation.
export function useAsync<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = []
): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading" });

  const run = useCallback(() => {
    let cancelled = false;
    setState({ status: "loading" });
    fetcher()
      .then((data) => {
        if (!cancelled) setState({ status: "success", data });
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setState({
            status: "error",
            error: err instanceof Error ? err.message : "Request failed.",
          });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => run(), [run]);

  return { ...state, reload: () => run() };
}
