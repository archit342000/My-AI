import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { showToast } from '../../components/ui/toast-store';
import { settingsApi, settingsKeys } from '../../api/settings';
import { Field, Section } from './forms';

const LEVELS: Array<['minimal' | 'advanced', string, string]> = [
  ['minimal', 'Minimal', 'Basic fingerprint hygiene. Fastest.'],
  ['advanced', 'Advanced', 'Stronger evasion for sites that block automation. Slower.'],
];

export function StealthDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const browser = useQuery({ queryKey: settingsKeys.browser, queryFn: settingsApi.getBrowser, enabled: open });
  const save = useMutation({
    mutationFn: (level: 'minimal' | 'advanced') => settingsApi.setBrowser(level),
    onSuccess: () => {
      showToast('Browser stealth updated', 'success');
      void queryClient.invalidateQueries({ queryKey: settingsKeys.browser });
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Save failed', 'error'),
  });
  const current = browser.data?.stealth_level ?? 'minimal';
  return (
    <Modal open={open} onClose={onClose} title="Browser stealth" maxWidth={480}>
      <Section title="Level">
        <div role="radiogroup" aria-label="Stealth level" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {LEVELS.map(([value, label, hint]) => (
            <Field key={value} label={label} hint={hint}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input type="radio" name="stealth-level" value={value} checked={current === value} onChange={() => save.mutate(value)} />
                <span>{label}</span>
              </label>
            </Field>
          ))}
        </div>
      </Section>
    </Modal>
  );
}
