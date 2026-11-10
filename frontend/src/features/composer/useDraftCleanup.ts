import { useEffect } from 'react';
import { useAttachmentStore } from '../../state/attachment-store';

/**
 * Deletes every staged-but-unsent file when the page is really being closed or reloaded (not when it only goes
 * into the back/forward cache), with a keepalive request so it survives the unload.
 */
export function useDraftCleanup(): void {
  useEffect(() => {
    function onPageHide(event: PageTransitionEvent) {
      if (event.persisted) return;
      const { lists, discard } = useAttachmentStore.getState();
      for (const key of Object.keys(lists)) void discard(key, { keepalive: true });
    }
    window.addEventListener('pagehide', onPageHide);
    return () => window.removeEventListener('pagehide', onPageHide);
  }, []);
}
