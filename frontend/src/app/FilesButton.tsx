import { useLocation } from 'react-router';
import { IconButton } from '../components/ui/Button';
import { useChatHasNoFiles } from '../features/artifacts/useChatHasNoFiles';
import { cx } from '../lib/cx';
import { useUiStore } from '../state/ui-store';

/**
 * Opens and closes the Files panel beside a chat. Shown on pages with a message box; switched off
 * on the home page (no chat yet) and dimmed while the chat has no files. Closing loses nothing:
 * the panel saves what is unsaved as it goes away.
 */
export function FilesButton() {
  const path = useLocation().pathname;
  const toggleArtifacts = useUiStore((s) => s.toggleArtifacts);
  const artifactsOpen = useUiStore((s) => s.artifactsOpen);
  const noFiles = useChatHasNoFiles();

  if (path !== '/' && !path.startsWith('/chat/')) return null;

  return (
    <IconButton
      id="nav-files-btn"
      icon="file"
      label="Files"
      aria-pressed={artifactsOpen}
      className={cx(noFiles && 'top-right-btn--empty')}
      disabled={path === '/'}
      onClick={toggleArtifacts}
    />
  );
}
