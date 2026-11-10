import { useEffect, useState } from 'react';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { IconButton } from '../../components/ui/Button';
import { showToast } from '../../components/ui/toast-store';

interface Props {
  text: string;
  role: 'user' | 'assistant';
  canRetry: boolean;
  onEdit?: () => void;
  onRetry?: () => void;
  onDelete: () => void;
}

const COPIED_MS = 1500;

/** Hover row under each message: copy, edit, retry and delete, as icon buttons with tooltips. */
export function MessageActions({ text, role, canRetry, onEdit, onRetry, onDelete }: Props) {
  const [confirming, setConfirming] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return undefined;
    const timer = window.setTimeout(() => setCopied(false), COPIED_MS);
    return () => window.clearTimeout(timer);
  }, [copied]);

  async function copy() {
    if (!navigator.clipboard) {
      showToast('Copying needs a secure (https) connection', 'error');
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Couldn't copy. Try again.", 'error');
    }
  }

  return (
    <>
      <div
        className={`message-actions-container ${role === 'user' ? 'user-actions' : 'bot-actions'}`}
      >
        <IconButton
          className="action-btn copy-msg-btn"
          size="sm"
          icon={copied ? 'check' : 'copy'}
          label={copied ? 'Copied' : 'Copy message'}
          onClick={() => void copy()}
        />
        {onEdit ? (
          <IconButton
            className="action-btn edit-msg-btn"
            size="sm"
            icon="edit"
            label="Edit message"
            onClick={onEdit}
          />
        ) : null}
        {canRetry && onRetry ? (
          <IconButton
            className="action-btn retry-msg-btn"
            size="sm"
            icon="refresh-cw"
            label="Retry response"
            onClick={onRetry}
          />
        ) : null}
        <IconButton
          className="action-btn delete-msg-btn"
          size="sm"
          tone="danger"
          icon="trash"
          label="Delete message"
          onClick={() => setConfirming(true)}
        />
      </div>
      <ConfirmDialog
        open={confirming}
        title="Delete message?"
        message="This removes the message from the chat. It cannot be undone."
        confirmLabel="Delete message"
        danger
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          onDelete();
        }}
      />
    </>
  );
}
