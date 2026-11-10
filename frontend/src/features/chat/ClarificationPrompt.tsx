import { useEffect, useRef, useState } from 'react';
import { clarificationApi } from '../../api/tools';
import { Markdown } from '../../components/markdown/Markdown';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Textarea } from '../../components/ui/Field';
import { RadioCards } from '../../components/ui/RadioCards';
import { showToast } from '../../components/ui/toast-store';
import type { ClarificationRequest } from '../../lib/clarification';
import { stopTurn } from './send-turn';

const CUSTOM = 'custom';

/**
 * The question a waiting turn has asked, with its options and a free answer. Answering posts it and the turn
 * continues; Cancel stops the turn (after a confirmation). The prompt hides as soon as the answer is accepted.
 */
export function ClarificationPrompt({
  chatId,
  request,
}: {
  chatId: string;
  request: ClarificationRequest;
}) {
  const [choice, setChoice] = useState('');
  const [custom, setCustom] = useState('');
  const [sending, setSending] = useState(false);
  const [answeredId, setAnsweredId] = useState<string | null>(null);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const section = useRef<HTMLElement>(null);
  // A prompt that appears below the fold is brought into view.
  useEffect(() => {
    section.current?.scrollIntoView?.({ block: 'nearest' });
  }, [request.id]);

  if (answeredId === request.id) return null;

  // Nothing is chosen until the user picks (an empty choice must not read as option 0).
  const answer =
    choice === ''
      ? ''
      : choice === CUSTOM
        ? custom.trim()
        : (request.options[Number(choice)] ?? '');

  async function confirm() {
    if (!answer) return;
    setSending(true);
    try {
      await clarificationApi.respond(chatId, request.id, answer);
      setAnsweredId(request.id);
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Could not send the answer', 'error');
    } finally {
      setSending(false);
    }
  }

  return (
    <section
      ref={section}
      className="clarify"
      role="group"
      aria-live="polite"
      aria-label="The assistant has a question"
    >
      <div className="clarify__question">
        <Markdown text={request.question} className="message-content raw-text-content" />
      </div>
      <RadioCards
        label="Answer"
        value={choice}
        onChange={setChoice}
        options={[
          ...request.options.map((option, index) => ({ value: String(index), title: option })),
          { value: CUSTOM, title: 'Custom response…' },
        ]}
      />
      {choice === CUSTOM ? (
        <Textarea
          className="clarify__custom"
          autoGrow
          autoFocus
          rows={2}
          aria-label="Your answer"
          placeholder="Type your answer"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
        />
      ) : null}
      <div className="clarify__actions">
        <Button variant="ghost" onClick={() => setConfirmingCancel(true)}>
          Cancel
        </Button>
        <Button
          variant="primary"
          disabled={!answer}
          loading={sending}
          onClick={() => void confirm()}
        >
          Confirm response
        </Button>
      </div>
      <ConfirmDialog
        open={confirmingCancel}
        title="Stop this reply?"
        message="The assistant is waiting for your answer. Cancelling stops the reply."
        confirmLabel="Stop reply"
        danger
        onCancel={() => setConfirmingCancel(false)}
        onConfirm={() => {
          setConfirmingCancel(false);
          void stopTurn();
        }}
      />
    </section>
  );
}
