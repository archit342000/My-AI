import { Link, useRouteError } from 'react-router';
import { DeadEnd } from '../components/ui/DeadEnd';
import { BrokeScreen } from './ErrorBoundary';

/** The way out every dead end offers. */
export function HomeLink({ primary = true }: { primary?: boolean }) {
  return (
    <Link
      to="/"
      className={primary ? 'ui-button ui-button--primary' : 'ui-button ui-button--secondary'}
    >
      Go to Home
    </Link>
  );
}

/** An address that leads nowhere. */
export function NotFoundPage() {
  return (
    <DeadEnd drawing="not-found" title="This page does not exist." actions={<HomeLink />}>
      The link may be old, or the address has a typing mistake.
    </DeadEnd>
  );
}

/** A chat or a workspace that was deleted, or never existed. */
export function GonePage({ what }: { what: 'chat' | 'workspace' }) {
  return (
    <DeadEnd drawing="gone" title={`This ${what} no longer exists.`} actions={<HomeLink />}>
      It may have been deleted, or the link is old.
    </DeadEnd>
  );
}

/** A page that failed while it was being drawn (the router's own safety net). */
export function RouteError() {
  const error = useRouteError();
  return <BrokeScreen error={error} onRetry={() => window.location.reload()} />;
}
