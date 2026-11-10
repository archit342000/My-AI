import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { modelsApi, settingsKeys } from '../../api/settings';
import { useSettingsStore } from '../../state/settings-store';
import { useChatDetail } from './useChatQueries';

/**
 * Makes an opened chat's own settings (modes, model, persona, sampling) the active ones, once per
 * chat, as soon as the chat and the model list have both loaded; a refetch of the same chat does not
 * overwrite what the user changed meanwhile. Leaving the chat (or opening another) puts the new-chat
 * defaults back, so the home page, a new chat and a temporary chat all start from them.
 */
export function useChatSettings(chatId: string | undefined): void {
  const detail = useChatDetail(chatId);
  // Same key and function as the composer, so both share one cached model list.
  const models = useQuery({
    queryKey: settingsKeys.models,
    queryFn: modelsApi.list,
    staleTime: 30_000,
  });
  const applied = useRef<string | null>(null);

  useEffect(() => {
    // The list is only needed to check the chat's model: if it cannot be loaded, the rest still applies.
    if (!chatId || !detail.data || (!models.data && !models.isError)) return;
    if (applied.current === chatId) return;
    applied.current = chatId;
    useSettingsStore.getState().applyChat(detail.data, models.data ?? []);
  }, [chatId, detail.data, models.data, models.isError]);

  // Cleanup runs when the chat changes or the page unmounts (and between StrictMode's two mounts,
  // which clears the marker so the second mount applies again).
  useEffect(() => {
    // Chat-scoped from the first moment, so nothing changed before the chat has loaded leaks into the defaults.
    if (chatId) useSettingsStore.getState().enterChat();
    return () => {
      applied.current = null;
      useSettingsStore.getState().resetToDefaults();
    };
  }, [chatId]);
}
