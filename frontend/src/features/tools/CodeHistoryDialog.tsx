import { skipToken, useQuery } from '@tanstack/react-query';
import { useMatch } from 'react-router';
import { codeExecApi } from '../../api/filesystem';
import { Modal } from '../../components/ui/Modal';
import { RunCard } from './RunCard';

/** Code-execution runs for the chat that is open. Live runs over the WebSocket are not wired yet. */
export function CodeHistoryDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  // The chat on screen, not whichever chat happens to be streaming.
  const id = useMatch('/chat/:chatId')?.params.chatId ?? null;
  const history = useQuery({
    queryKey: ['code-history', id],
    // No chat open (or the dialog closed): there is nothing to ask for.
    queryFn: open && id !== null ? () => codeExecApi.history(id) : skipToken,
  });
  return (
    <Modal open={open} onClose={onClose} title="Code execution history" maxWidth={720}>
      {id === null ? <p className="tool-dialog__note">Open a chat to see its runs.</p> : null}
      {id !== null && history.isPending ? <p className="tool-dialog__note">Loading…</p> : null}
      {history.isError ? (
        <div role="alert" className="tool-dialog__error">
          Could not load the runs: {history.error.message}
        </div>
      ) : null}
      {history.data && history.data.length === 0 ? (
        <p className="tool-dialog__note">No runs yet.</p>
      ) : null}
      {(history.data ?? []).map((run) => (
        <RunCard key={run.id} run={run} />
      ))}
    </Modal>
  );
}
