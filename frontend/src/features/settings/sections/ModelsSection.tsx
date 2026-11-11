import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { modelsApi, settingsKeys, SETTINGS_STALE_MS } from '../../../api/settings';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Field';
import { HoldScreen } from '../../../components/ui/HoldScreen';
import { StatusLight } from '../../../components/ui/StatusLight';
import { showToast } from '../../../components/ui/toast-store';
import { sortModels } from '../../../lib/model-options';
import { SettingsSection, SubHead } from '../forms';
import { SpeedTestPanel } from '../SpeedTestPanel';

/** How often the list is read: slowly at rest, quickly while a model is being loaded. */
const POLL_MS = 5000;
const POLL_LOADING_MS = 1500;
/** The longest the whole-screen wait stays up. A load that takes longer carries on behind the page. */
const HOLD_MAX_MS = 180_000;
/** A list is only worth searching once it is this long. */
const SEARCH_FROM = 6;

/**
 * Models (admin): what is loaded, load and unload, and the speed test. Loading a model makes the
 * server free memory first, so the whole screen waits until the model is ready.
 */
export function ModelsSection() {
  const queryClient = useQueryClient();
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const models = useQuery({
    queryKey: settingsKeys.models,
    queryFn: modelsApi.list,
    staleTime: SETTINGS_STALE_MS,
    refetchInterval: loadingId ? POLL_LOADING_MS : POLL_MS,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: settingsKeys.models });
  const all = sortModels(models.data ?? []);
  const shown = all.filter((m) => m.id.toLowerCase().includes(query.trim().toLowerCase()));

  // The wait ends when the model reports loaded, or after the longest time it may take.
  const held = all.find((m) => m.id === loadingId);
  const heldLoaded = held?.status?.value === 'loaded';
  const started = useRef(0);
  useEffect(() => {
    if (!loadingId) return undefined;
    if (heldLoaded) {
      setLoadingId(null);
      showToast(`${loadingId} is ready`, 'success');
      return undefined;
    }
    const left = Math.max(0, HOLD_MAX_MS - (Date.now() - started.current));
    const timer = window.setTimeout(() => {
      setLoadingId(null);
      showToast(`${loadingId} is still loading. It will show as loaded when it is ready.`, 'info');
    }, left);
    return () => window.clearTimeout(timer);
  }, [loadingId, heldLoaded]);

  async function load(id: string) {
    started.current = Date.now();
    setLoadingId(id);
    try {
      await modelsApi.load(id);
      await refresh();
    } catch (err) {
      setLoadingId(null);
      showToast(
        err instanceof Error ? err.message : `${id} could not be loaded. Try again.`,
        'error',
      );
    }
  }

  async function unload(id: string) {
    setBusyId(id);
    try {
      await modelsApi.unload(id);
      await refresh();
    } catch (err) {
      showToast(
        err instanceof Error ? err.message : `${id} could not be unloaded. Try again.`,
        'error',
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <SettingsSection id="models" title="Models">
      {all.length >= SEARCH_FROM ? (
        <div className="crud-toolbar">
          <Input
            type="search"
            aria-label="Search models"
            placeholder="Search models"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      ) : null}
      <ul className="crud-list model-list">
        {shown.map((m) => {
          const status = m.status?.value;
          const loading = status === 'loading';
          const loaded = status === 'loaded';
          return (
            <li key={m.id} className="crud-row">
              <div className="crud-text">
                <div className="crud-title">
                  <span className="crud-title__name font-mono" title={m.id}>
                    {m.id}
                  </span>
                  <StatusLight
                    label={
                      loaded
                        ? 'Loaded'
                        : loading
                          ? 'Loading'
                          : status
                            ? 'Not loaded'
                            : 'Status unknown'
                    }
                    tone={loaded ? 'ok' : loading ? 'neutral' : 'off'}
                    busy={loading}
                  />
                </div>
              </div>
              {loaded ? (
                <Button
                  variant="secondary"
                  className="model-row__action"
                  loading={busyId === m.id}
                  onClick={() => void unload(m.id)}
                >
                  Unload
                </Button>
              ) : (
                <Button
                  variant="quiet"
                  className="model-row__action"
                  disabled={loading}
                  onClick={() => void load(m.id)}
                >
                  Load
                </Button>
              )}
            </li>
          );
        })}
      </ul>
      {models.isPending ? (
        <p className="ui-hint crud-none" role="status">
          Loading the models
        </p>
      ) : shown.length === 0 ? (
        <p className="ui-hint crud-none">
          {query.trim() ? 'Nothing matches.' : 'No models found.'}
        </p>
      ) : null}
      {models.isError ? (
        <p className="ui-hint crud-none" role="alert">
          The models could not be listed. Check that the model server is running.
        </p>
      ) : null}

      <SubHead>Speed test</SubHead>
      <SpeedTestPanel models={models.data ?? []} />

      <HoldScreen open={loadingId !== null} title="Switching models">
        Freeing up memory, then loading {loadingId}. This can take a minute.
      </HoldScreen>
    </SettingsSection>
  );
}
