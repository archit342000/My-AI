import { describe, expect, it } from 'vitest';
import { shouldDiscardTemporaryChat } from './temporary-chat';

describe('shouldDiscardTemporaryChat (F-10)', () => {
  it('keeps a temporary chat started from a chat page when the move to / commits', () => {
    expect(shouldDiscardTemporaryChat('/chat/x', '/', true)).toBe(false);
  });
  it('discards it when the user leaves the landing page', () => {
    expect(shouldDiscardTemporaryChat('/', '/chat/y', true)).toBe(true);
  });
  it('does nothing without a temporary chat or without a navigation', () => {
    expect(shouldDiscardTemporaryChat('/', '/chat/y', false)).toBe(false);
    expect(shouldDiscardTemporaryChat('/chat/x', '/chat/x', true)).toBe(false);
  });
});
