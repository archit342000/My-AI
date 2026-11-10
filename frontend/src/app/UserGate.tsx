import { useEffect, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ApiError, shouldRetryQuery } from '../api/client';
import { meApi, meKeys } from '../api/me';
import { Button } from '../components/ui/Button';
import { DeadEnd } from '../components/ui/DeadEnd';
import { StatusLight } from '../components/ui/StatusLight';
import { initUserStorage } from '../lib/user-storage';
import { useSettingsStore } from '../state/settings-store';
import { useUserStore } from '../state/user-store';

function reload() {
  window.location.reload();
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
    const expired = error instanceof ApiError && error.status === 401;
    return (
      <DeadEnd
        drawing={expired ? 'gone' : 'broke'}
        title={expired ? 'Your session has ended.' : "Couldn't load your account."}
        details={expired || !(error instanceof Error) ? undefined : error.message}
        actions={
          <Button variant="primary" onClick={reload}>
            {expired ? 'Sign in again' : 'Try again'}
          </Button>
        }
      >
        {expired
          ? 'Sign in again to carry on. Nothing you saved is lost.'
          : 'The app is not answering. Check your connection, then try again.'}
      </DeadEnd>
    );
  }
  if (!ready) {
    return (
      <div className="gate-wait">
        <StatusLight label="Loading" busy />
      </div>
    );
  }
  return <>{children}</>;
}
