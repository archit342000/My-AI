import { useQuery } from '@tanstack/react-query';
import { portalApi } from '../../api/filesystem';
import { Modal } from '../../components/ui/Modal';

/** Remote browser session (noVNC) shown in a large overlay. Initialised on open. */
export function PortalDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const session = useQuery({ queryKey: ['portal'], queryFn: portalApi.init, enabled: open, staleTime: 0, gcTime: 0 });
  return (
    <Modal open={open} onClose={onClose} title="Browser portal" maxWidth={1100}>
      {session.isPending ? <div style={{ color: 'var(--content-muted)' }}>Starting browser session…</div> : null}
      {session.isError ? <div role="alert" style={{ color: 'var(--color-rose-500)' }}>{session.error.message}</div> : null}
      {session.isSuccess ? (
        <iframe title="Remote browser" src="/api/tools/portal/vnc/" style={{ width: '100%', height: '70vh', border: 0, borderRadius: 12, background: '#000' }} />
      ) : null}
    </Modal>
  );
}
