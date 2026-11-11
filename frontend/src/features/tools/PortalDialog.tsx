import { useQuery } from '@tanstack/react-query';
import { portalApi } from '../../api/filesystem';
import { Button } from '../../components/ui/Button';
import { StatusLight } from '../../components/ui/StatusLight';
import { Window } from '../../components/ui/Window';

/**
 * The browser window: the AI's own browser, shown live. It starts a session when it opens and says
 * whether it is starting, live or not running (with a way to try again).
 */
export function PortalDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const session = useQuery({
    queryKey: ['portal'],
    queryFn: portalApi.init,
    enabled: open,
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });
  const starting = session.isPending || session.isRefetching;
  const status = starting ? (
    <StatusLight label="Starting" busy />
  ) : session.isError ? (
    <StatusLight label="Not running" tone="bad" />
  ) : (
    <StatusLight label="Live" tone="ok" />
  );
  return (
    <Window open={open} onClose={onClose} title="Browser window" status={status}>
      <div className="tool-window">
        {/* The remote screen is a picture of another computer: it keeps its own dark surround day and night. */}
        <div className="portal-screen">
          {starting ? (
            <div className="portal-wait" role="status">
              <div className="portal-wait__bars" aria-hidden="true">
                <i />
                <i />
              </div>
              <span>Starting the browser</span>
            </div>
          ) : session.isError ? (
            <div className="portal-fail" role="alert">
              <span>The browser did not start.</span>
              <span className="portal-fail__why">{session.error.message}</span>
              <Button variant="secondary" onClick={() => void session.refetch()}>
                Try again
              </Button>
            </div>
          ) : (
            <iframe
              title="Remote browser"
              className="portal-frame"
              src="/api/tools/portal/vnc/vnc.html?autoconnect=true&resize=scale&path=api/tools/portal/ws"
            />
          )}
        </div>
        <p className="ui-hint tool-window__hint">
          This is the AI's own browser. You can click and type in it yourself, for example to sign
          in to a site for it.
        </p>
      </div>
    </Window>
  );
}
