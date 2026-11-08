import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { Modal } from '../../components/ui/Modal';
import { RadioCards } from '../../components/ui/RadioCards';
import { showToast } from '../../components/ui/toast-store';
import { settingsApi, settingsKeys } from '../../api/settings';
import { SETTINGS_STALE_MS } from '../../api/settings';

type StealthLevel = 'minimal' | 'advanced';

const LEVELS = [
  { value: 'minimal', title: 'Minimal', description: 'Basic fingerprint hygiene. Fastest.' },
  { value: 'advanced', title: 'Advanced', description: 'Stronger evasion for sites that block automation. Slower.' },
];

export function StealthDialog({ open, onClose, onBack }: { open: boolean; onClose: () => void; onBack?: () => void }) {
  const queryClient = useQueryClient();
  const browser = useQuery({ queryKey: settingsKeys.browser, queryFn: settingsApi.getBrowser, enabled: open, staleTime: SETTINGS_STALE_MS });
  const save = useMutation({
    mutationFn: (level: StealthLevel) => settingsApi.setBrowser(level),
    onSuccess: () => {
      showToast('Saved', 'success');
      void queryClient.invalidateQueries({ queryKey: settingsKeys.browser });
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Save failed', 'error'),
  });
  const current = browser.data?.stealth_level ?? 'minimal';
  return (
    <Modal open={open} onClose={onClose} onBack={onBack} title="Browser stealth" maxWidth={480}>
      <RadioCards
        label="Stealth level"
        value={current}
        options={LEVELS}
        onChange={(value) => save.mutate(value as StealthLevel)}
      />
    </Modal>
  );
}
