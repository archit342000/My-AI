import { useState } from 'react';
import { useLocation } from 'react-router';
import { IconButton } from '../components/ui/Button';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { useChatHasNoFiles } from '../features/artifacts/useChatHasNoFiles';
import { cx } from '../lib/cx';
import { useUiStore } from '../state/ui-store';

/**
 * Opens and closes the Files panel beside a chat. Shown on pages with a message box; switched off
 * on the home page (no chat yet) and dimmed while the chat has no files. Closing with unsaved
 * edits asks first.
 */
export function FilesButton() {
  const path = useLocation().pathname;
  const toggleArtifacts = useUiStore((s) => s.toggleArtifacts);
  const artifactsOpen = useUiStore((s) => s.artifactsOpen);
  const artifactsDirty = useUiStore((s) => s.artifactsDirty);
  const noFiles = useChatHasNoFiles();
  const [confirmClose, setConfirmClose] = useState(false);

  if (path !== '/' && !path.startsWith('/chat/')) return null;

  return (
    <>
      <IconButton
        id="nav-files-btn"
        icon="file"
        label="Files"
        aria-pressed={artifactsOpen}
        className={cx(noFiles && 'top-right-btn--empty')}
        disabled={path === '/'}
        onClick={() =>
          artifactsOpen && artifactsDirty ? setConfirmClose(true) : toggleArtifacts()
        }
      />
      <ConfirmDialog
        open={confirmClose}
        title="Discard unsaved changes?"
        message="The open file has changes that are not saved. Closing the files panel drops them."
        confirmLabel="Discard changes"
        danger
        onCancel={() => setConfirmClose(false)}
        onConfirm={() => {
          setConfirmClose(false);
          toggleArtifacts();
        }}
      />
    </>
  );
}
