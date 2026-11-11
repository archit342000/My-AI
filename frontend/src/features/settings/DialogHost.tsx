import { useModalStore } from '../../state/modal-store';
import { useIsAdmin } from '../../state/user-store';
import { CodeHistoryDialog } from '../tools/CodeHistoryDialog';
import { PortalDialog } from '../tools/PortalDialog';

/** Renders whichever tool window is open. Mounted once in the root layout. */
export function DialogHost() {
  const isAdmin = useIsAdmin();
  const open = useModalStore((s) => s.open);
  const close = useModalStore((s) => s.close);
  return (
    <>
      {/* The browser window is admin-only: it is not mounted for a user, so a stray show('portal') cannot open it. */}
      {isAdmin ? <PortalDialog open={open === 'portal'} onClose={close} /> : null}
      <CodeHistoryDialog open={open === 'code-history'} onClose={close} />
    </>
  );
}
