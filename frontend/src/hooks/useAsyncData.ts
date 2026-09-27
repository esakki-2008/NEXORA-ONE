import { useCallback, useEffect, useState } from "react";

export interface AsyncDataState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  updatedAt: Date | null;
  reload: () => void;
}

function errorMessage(reason: unknown): string {
  if (reason instanceof Error) return reason.message;
  return "The request could not be completed.";
}

/** A small request lifecycle primitive shared by route-level screens. */
export function useAsyncData<T>(
  loader: () => Promise<T>,
  dependencies: readonly unknown[] = []
): AsyncDataState<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);

    loader()
      .then((payload) => {
        if (!active) return;
        setData(payload);
        setUpdatedAt(new Date());
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(errorMessage(reason));
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [loader, reloadToken, ...dependencies]);

  return { data, isLoading, error, updatedAt, reload };
}
