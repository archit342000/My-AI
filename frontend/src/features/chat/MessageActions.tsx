import { useState } from 'react';
import { Icon } from '../../components/icons/Icon';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { showToast } from '../../components/ui/toast-store';

interface Props {
  text: string;
  role: 'user' | 'assistant';
  canRetry: boolean;
  onEdit?: () => void;
  onRetry?: () => void;
  onDelete: () => void;
}

/** Hover row under each message (legacy `.message-actions-container`). */
export function MessageActions({ text, role, canRetry, onEdit, onRetry, onDelete }: Props) {
  const [confirming, setConfirming] = useState(false);
  return (
    <>
      <div className={`message-actions-container ${role === 'user' ? 'user-actions' : 'bot-actions'}`}>
        <button type="button" className="action-btn copy-msg-btn" title="Copy" aria-label="Copy message"
          onClick={() => {
            void navigator.clipboard?.writeText(text);
            showToast('Copied to clipboard', 'success');
          }}>
          <Icon name="file-text" size={14} />
        </button>
        {onEdit ? (
          <button type="button" className="action-btn edit-msg-btn" title="Edit" aria-label="Edit message" onClick={onEdit}>
            <Icon name="edit" size={14} />
          </button>
        ) : null}
        {canRetry && onRetry ? (
          <button type="button" className="action-btn retry-msg-btn" title="Retry" aria-label="Retry response" onClick={onRetry}>
            <Icon name="zap" size={14} />
          </button>
        ) : null}
        <button type="button" className="action-btn delete-msg-btn" title="Delete" aria-label="Delete message" onClick={() => setConfirming(true)}>
          <Icon name="trash" size={14} />
        </button>
      </div>
      <ConfirmDialog
        open={confirming}
        title="Delete message?"
        message="This removes the message from the chat. It cannot be undone."
        confirmLabel="Delete"
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
