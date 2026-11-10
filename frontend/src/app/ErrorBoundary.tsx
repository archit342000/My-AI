import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button } from '../components/ui/Button';
import { DeadEnd } from '../components/ui/DeadEnd';

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

/** What is shown when the app itself fails: nothing technical first, and two ways on. */
export function BrokeScreen({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const details =
    error instanceof Error ? `${error.name}: ${error.message}` : error ? String(error) : undefined;
  return (
    <DeadEnd
      drawing="broke"
      title="Something broke on our side."
      details={details}
      actions={
        <>
          {onRetry ? (
            <Button variant="primary" onClick={onRetry}>
              Try again
            </Button>
          ) : null}
          <Button variant="secondary" onClick={() => window.location.assign('/')}>
            Go to Home
          </Button>
        </>
      }
    >
      Nothing you did. Your work up to the last save is safe.
    </DeadEnd>
  );
}

/**
 * Catches a failure while drawing the screen and shows the "something broke" dead end instead of a
 * blank page. Try again draws the screen once more.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('The screen could not be drawn', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <BrokeScreen error={this.state.error} onRetry={() => this.setState({ error: null })} />
      );
    }
    return this.props.children;
  }
}
