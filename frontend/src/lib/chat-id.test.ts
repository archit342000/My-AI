import { describe, expect, it } from 'vitest';
import { generateChatId } from './chat-id';

describe('generateChatId', () => {
  it('is a non-empty lowercase alphanumeric id', () => {
    expect(generateChatId()).toMatch(/^[a-z0-9]{8,}$/);
  });
  it('differs between calls', () => {
    expect(new Set(Array.from({ length: 50 }, generateChatId)).size).toBe(50);
  });
});
