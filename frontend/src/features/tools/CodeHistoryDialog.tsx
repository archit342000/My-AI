import { skipToken, useQuery } from '@tanstack/react-query';
import { useMatch } from 'react-router';
import { codeExecApi } from '../../api/filesystem';
import { EmptyState } from '../../components/ui/EmptyState';
import { Notice } from '../../components/ui/Notice';
import { Window } from '../../components/ui/Window';
import { RunCard } from './RunCard';

/** The code runs of the chat that is open, newest first: each folds open to its code and output. */
export function CodeHistoryDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  // The chat on screen, not whichever chat happens to be streaming.
  const id = useMatch('/chat/:chatId')?.params.chatId ?? null;
  const history = useQuery({
    queryKey: ['code-history', id],
    // No chat open (or the window closed): there is nothing to ask for.
    queryFn: open && id !== null ? () => codeExecApi.history(id) : skipToken,
  });
  const runs = history.data ?? [];
  const count =
    history.data && runs.length > 0 ? (
      <span className="dat keep">
        {runs.length} {runs.length === 1 ? 'run' : 'runs'}
      </span>
    ) : undefined;
  return (
    <Window
      open={open}
      onClose={onClose}
      title="Code run history"
      status={count}
      maxWidth="min(52rem, 100%)"
    >
      <div className="tool-window">
        {id === null ? (
          <EmptyState
            title="Open a chat first"
            description="Runs are listed for the chat that is open."
          />
        ) : history.isError ? (
          <Notice tone="bad" actionLabel="Try again" onAction={() => void history.refetch()}>
            The runs could not be loaded. {history.error.message}
          </Notice>
        ) : history.isPending ? (
          <div className="loglist" role="status" aria-label="Loading the runs">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="log-row log-row--placeholder" aria-hidden="true" />
            ))}
          </div>
        ) : runs.length === 0 ? (
          <EmptyState
            title="No code has been run yet"
            description="When the AI runs code in this chat, each run is listed here."
          />
        ) : (
          <div className="loglist code-runs">
            {runs.map((run, i) => (
              <RunCard key={run.id} run={run} defaultOpen={i === 0} />
            ))}
          </div>
        )}
      </div>
    </Window>
  );
}
