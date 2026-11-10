import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { showToast } from '../../components/ui/toast-store';
import { modelsApi, settingsKeys } from '../../api/settings';
import { Section } from './forms';
import { SpeedTestPanel } from './SpeedTestPanel';
import { Input } from '../../components/ui/Field';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { sortModels } from '../../lib/model-options';
import { SETTINGS_STALE_MS } from '../../api/settings';

/** Model manager: load/unload instances and run the speed test. */
export function ModelsDialog({ open, onClose, onBack }: { open: boolean; onClose: () => void; onBack?: () => void }) {
  const queryClient = useQueryClient();
  const models = useQuery({ queryKey: settingsKeys.models, queryFn: modelsApi.list, enabled: open, staleTime: SETTINGS_STALE_MS, refetchInterval: open ? 5000 : false });
  const [query, setQuery] = useState('');
  const refresh = () => queryClient.invalidateQueries({ queryKey: settingsKeys.models });

  const load = useMutation({
    mutationFn: (id: string) => modelsApi.load(id),
    onSuccess: (_d, id) => {
      showToast(`Loading ${id}`, 'info');
      void refresh();
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Load failed', 'error'),
  });

  const unload = useMutation({
    mutationFn: (id: string) => modelsApi.unload(id),
    onSuccess: () => void refresh(),
    onError: (e) => showToast(e instanceof Error ? e.message : 'Unload failed', 'error'),
  });

  return (
    <Modal open={open} onClose={onClose} onBack={onBack} title="Model manager" maxWidth={680}>
      <Section title="Instances">
        <Input
          type="search"
          aria-label="Search loaded and available models"
          placeholder="Search models"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <ul className="model-list">
          {sortModels(models.data ?? []).filter((m) => m.id.toLowerCase().includes(query.trim().toLowerCase())).map((m) => {
            const status = m.status?.value;
            const loading = status === 'loading';
            const loaded = status === 'loaded';
            return (
              <li key={m.id} className="model-row">
                <span className="model-row__name" title={m.id}>{m.id}</span>
                <Badge tone={loaded ? 'success' : loading ? 'warning' : 'neutral'}>
                  {loading ? <span className="ui-spinner" aria-hidden="true" /> : null}
                  {loaded ? 'Loaded' : loading ? 'Loading' : status ? 'Unloaded' : 'Status unknown'}
                </Badge>
                {loaded ? (
                  <Button variant="secondary" size="sm" className="model-row__action" onClick={() => unload.mutate(m.id)}>Unload</Button>
                ) : (
                  <Button variant="secondary" size="sm" className="model-row__action" disabled={loading} onClick={() => load.mutate(m.id)}>Load</Button>
                )}
              </li>
            );
          })}
        </ul>
        {models.isPending ? <div className="model-list__status">Loading…</div> : null}
      </Section>

      <SpeedTestPanel models={models.data ?? []} />
    </Modal>
  );
}
