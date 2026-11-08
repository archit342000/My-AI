import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { showToast } from '../../components/ui/toast-store';
import { modelsApi, settingsKeys } from '../../api/settings';
import { Field, Section, Status, inputStyle } from './forms';

/** Model manager: load/unload instances and run the speed test. */
export function ModelsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const models = useQuery({ queryKey: settingsKeys.models, queryFn: modelsApi.list, enabled: open, refetchInterval: open ? 5000 : false });
  const [target, setTarget] = useState('');
  const [result, setResult] = useState<string | null>(null);
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
    <Modal open={open} onClose={onClose} title="Model manager" maxWidth={680}>
      <Section title="Instances">
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {(models.data ?? []).map((m) => (
            <li key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{m.id}</span>
              <span style={{ fontSize: '0.75rem', color: m.status.value === 'loaded' ? 'var(--color-emerald-500)' : 'var(--content-muted)' }}>{m.status.value}</span>
              {m.status.value === 'loaded' ? (
                <button type="button" className="btn-secondary" onClick={() => unload.mutate(m.id)}>Unload</button>
              ) : (
                <button type="button" className="btn-secondary" onClick={() => load.mutate(m.id)}>Load</button>
              )}
            </li>
          ))}
        </ul>
        {models.isPending ? <div style={{ color: 'var(--content-muted)' }}>Loading…</div> : null}
      </Section>

      <Section title="Speed test">
        <Field label="Model">
          <select style={inputStyle} value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="">Select a model</option>
            {(models.data ?? []).map((m) => <option key={m.id} value={m.id}>{m.id}</option>)}
          </select>
        </Field>
        <button type="button" className="btn-primary" disabled={!target || speed.isPending} onClick={() => { setResult(null); speed.mutate(); }}>
          {speed.isPending ? 'Running…' : 'Run speed test'}
        </button>
        {result ? <pre className="font-mono" style={{ marginTop: 12, whiteSpace: 'pre-wrap', fontSize: '0.75rem' }}>{result}</pre> : null}
        <Status message={speed.isError ? 'Speed test failed' : null} tone="error" />
      </Section>
    </Modal>
  );
}
