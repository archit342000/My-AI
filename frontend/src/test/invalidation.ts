import { queryKeys } from '../api/chats';

/** True when a spy on `queryClient.invalidateQueries` was called for the sidebar chat list. */
export function chatListInvalidated(spy: { mock: { calls: unknown[][] } }): boolean {
  const wanted = JSON.stringify(queryKeys.chats);
  return spy.mock.calls.some(([filters]) => {
    const key = (filters as { queryKey?: unknown } | undefined)?.queryKey;
    return JSON.stringify(key) === wanted;
  });
}
