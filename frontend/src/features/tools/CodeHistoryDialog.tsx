import { useQuery } from '@tanstack/react-query';
import { codeExecApi } from '../../api/filesystem';
import { Modal } from '../../components/ui/Modal';
import { useStreamStore } from '../../state/stream-store';

/** Code-execution runs for the current chat. Live runs over the WebSocket are not wired yet. */
export function CodeHistoryDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const chatId = useStreamStore((s) => s.chatId);
  const current = typeof window !== 'undefined' ? window.location.pathname.match(/^\/chat\/([^/]+)/)?.[1] ?? null : null;
  const id = chatId ?? current;
  const history = useQuery({
    queryKey: ['code-history', id],
    queryFn: () => codeExecApi.history(id as string),
    enabled: open && Boolean(id),
  });
  return (
    <Modal open={open} onClose={onClose} title="Code execution history" maxWidth={720}>
      {!id ? <div style={{ color: 'var(--content-muted)' }}>Open a chat to see its runs.</div> : null}
      {history.isPending && id ? <div style={{ color: 'var(--content-muted)' }}>Loading…</div> : null}
      {history.data && history.data.length === 0 ? <div style={{ color: 'var(--content-muted)' }}>No runs yet.</div> : null}
      {(history.data ?? []).map((run, i) => (
        <pre key={i} className="font-mono" style={{ whiteSpace: 'pre-wrap', fontSize: '0.75rem', padding: 8, borderRadius: 8, background: 'var(--surface-secondary)', marginBottom: 8 }}>
          {JSON.stringify(run, null, 2)}
        </pre>
      ))}
    </Modal>
  );
}
