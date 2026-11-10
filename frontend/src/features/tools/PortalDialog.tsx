import { useQuery } from '@tanstack/react-query';
import { portalApi } from '../../api/filesystem';
import { Modal } from '../../components/ui/Modal';

/** Remote browser session (noVNC) shown in a large overlay. Initialised on open. */
export function PortalDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const session = useQuery({ queryKey: ['portal'], queryFn: portalApi.init, enabled: open, staleTime: 0, gcTime: 0 });
  return (
    <Modal open={open} onClose={onClose} title="Browser portal" maxWidth={1100}>
      {session.isPending ? <p className="tool-dialog__note">Starting browser session…</p> : null}
      {session.isError ? (
        <div role="alert" className="tool-dialog__error">
          {session.error.message}
        </div>
      ) : null}
      {session.isSuccess ? (
        <iframe
          title="Remote browser"
          className="portal-frame"
          src="/api/tools/portal/vnc/vnc.html?autoconnect=true&resize=scale&path=api/tools/portal/ws"
        />
      ) : null}
    </Modal>
  );
}
