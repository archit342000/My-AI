import { apiRequest } from './client';

export const clarificationApi = {
  /** Answers a pending clarification request; the waiting turn then continues. Rejects with the server's message. */
  respond: (chatId: string, callbackId: string, content: string) =>
    apiRequest('/api/tools/clarification/response', {
      method: 'POST',
      json: { callback_id: callbackId, chat_id: chatId, type: 'answer', content },
    }),
};
