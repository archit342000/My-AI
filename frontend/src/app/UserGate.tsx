import { useEffect, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, shouldRetryQuery } from '../api/client';
import { meApi, meKeys } from '../api/me';
import { initUserStorage } from '../lib/user-storage';
import { useSettingsStore } from '../state/settings-store';
import { useUserStore } from '../state/user-store';

function reload() {
  window.location.reload();
}

/** A full-page message with a Reload button, shown before the app frame exists. */
function GateMessage({ text }: { text: string }) {
  return (
    <div className="chat-error" role="alert">
      <p>{text}</p>
      <button type="button" className="btn-secondary" onClick={reload}>
        Reload
      </button>
    </div>
  );
}

/**
 * Loads the signed-in user (`GET /api/me`) before anything user-dependent renders: it records the user,
 * switches localStorage to that user's keys and loads their saved settings, then renders the children.
 */
export function UserGate({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const { data, error } = useQuery({
    queryKey: meKeys.current,
    queryFn: meApi.get,
    staleTime: Infinity,
    // A 401 is final (the session ended): never retried, like any 403.
    retry: shouldRetryQuery,
  });

  useEffect(() => {
    if (!data) return;
    initUserStorage(data);
    useUserStore.getState().setUser(data);
    useSettingsStore.getState().hydrate();
    setReady(true);
  }, [data]);

  if (error) {
    return error instanceof ApiError && error.status === 401 ? (
      <GateMessage text="Your session has expired." />
    ) : (
      <GateMessage text="Couldn't load your account." />
    );
  }
  if (!ready) return <div className="chat-error">Loading…</div>;
  return <>{children}</>;
}
