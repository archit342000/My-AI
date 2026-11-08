import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { showToast } from '../../components/ui/toast-store';
import { modelsApi, settingsKeys } from '../../api/settings';
import { Section, Status } from './forms';
import { Input } from '../../components/ui/Field';
import { Select } from '../../components/ui/Select';
import { Field as UiField } from '../../components/ui/Field';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { modelSelectOptions, sortModels } from '../../lib/model-options';
import { SETTINGS_STALE_MS } from '../../api/settings';

/** Model manager: load/unload instances and run the speed test. */
export function ModelsDialog({ open, onClose, onBack }: { open: boolean; onClose: () => void; onBack?: () => void }) {
  const queryClient = useQueryClient();
  const models = useQuery({ queryKey: settingsKeys.models, queryFn: modelsApi.list, enabled: open, staleTime: SETTINGS_STALE_MS, refetchInterval: open ? 5000 : false });
  const [target, setTarget] = useState('');
  const [result, setResult] = useState<string | null>(null);
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

  const speed = useMutation({
    mutationFn: () => modelsApi.testSpeed(target, 4096),
    onSuccess: (r) => setResult(JSON.stringify(r, null, 2)),
    onError: (e) => setResult(e instanceof Error ? e.message : 'Speed test failed'),
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
            const loading = m.status.value === 'loading';
            const loaded = m.status.value === 'loaded';
            return (
              <li key={m.id} className="model-row">
                <span className="model-row__name" title={m.id}>{m.id}</span>
                <Badge tone={loaded ? 'success' : loading ? 'warning' : 'neutral'}>
                  {loading ? <span className="ui-spinner" aria-hidden="true" /> : null}
                  {loaded ? 'Loaded' : loading ? 'Loading' : 'Unloaded'}
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

      <Section title="Speed test">
        <UiField label="Model">
          {(c) => (
            <Select
              id={c.id}
              placeholder="Select a model"
              searchable
              searchPlaceholder="Search models"
              value={target}
              options={modelSelectOptions(models.data ?? [])}
              onChange={setTarget}
            />
          )}
        </UiField>
        <Button variant="primary" disabled={!target || speed.isPending} onClick={() => { setResult(null); speed.mutate(); }}>
          {speed.isPending ? 'Running…' : 'Run speed test'}
        </Button>
        {result ? <pre className="font-mono model-result">{result}</pre> : null}
        <Status message={speed.isError ? 'Speed test failed' : null} tone="error" />
      </Section>
    </Modal>
  );
}
