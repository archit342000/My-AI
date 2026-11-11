import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { chatsApi, queryKeys } from '../../api/chats';
import { showToast } from '../../components/ui/toast-store';
import { resumeTurn } from './send-turn';

/** Offered under a chat whose last turn was interrupted: continue it, or dismiss for good. */
export function ResumeBanner({ chatId }: { chatId: string }) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);

  async function dismiss() {
    setBusy(true);
    try {
      await chatsApi.patch(chatId, { resume_suppressed: 1 });
      await queryClient.invalidateQueries({ queryKey: queryKeys.chat(chatId) });
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Couldn't dismiss this. Try again.", 'error');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div id="resume-banner" className="resume-banner" role="status">
      <div className="resume-banner-content">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polygon points="5 3 19 12 5 21 5 3" />
        </svg>
        <span>This conversation was interrupted. Resume where it left off?</span>
      </div>
      <div className="resume-banner-actions">
        <button
          type="button"
          className="ui-button ui-button--ghost resume-dismiss"
          disabled={busy}
          onClick={() => void dismiss()}
        >
          Dismiss
        </button>
        <button
          type="button"
          className="ui-button ui-button--primary resume-confirm"
          onClick={() => void resumeTurn(queryClient, chatId)}
        >
          Resume
        </button>
      </div>
    </div>
  );
}
