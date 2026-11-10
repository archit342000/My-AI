/** Same id shape as the legacy `generateId()`. */
export function generateChatId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2);
}
