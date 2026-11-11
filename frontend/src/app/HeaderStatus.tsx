import { OnSphere } from '../components/background/OnSphere';
import { StatusLight } from '../components/ui/StatusLight';
import { useOnline } from '../hooks/useOnline';
import { useStreamStore } from '../state/stream-store';

/**
 * The status light in the app header: Ready, Thinking while a reply is being written, Stopping,
 * or Offline. On an open screen it sits on the sphere, so it carries the fade (rule book 3.3).
 */
export function HeaderStatus({ onSphere }: { onSphere: boolean }) {
  const busy = useStreamStore((s) => s.chatId !== null);
  const stopping = useStreamStore((s) => s.stopping);
  const online = useOnline();

  const light = !online ? (
    <StatusLight label="Offline" tone="warn" />
  ) : stopping ? (
    <StatusLight label="Stopping" busy />
  ) : busy ? (
    <StatusLight label="Thinking" busy />
  ) : (
    <StatusLight label="Ready" />
  );
  return onSphere ? (
    <OnSphere className="main-status">{light}</OnSphere>
  ) : (
    <div className="main-status">{light}</div>
  );
}
