import { useModalStore } from '../../state/modal-store';
import { AgentConfigDialog } from './AgentConfigDialog';
import { ChatSettingsModal } from './ChatSettingsModal';
import { ModelsDialog } from './ModelsDialog';
import { PersonasDialog } from './PersonasDialog';
import { PreferencesDialog } from './PreferencesDialog';
import { SkillsDialog } from './SkillsDialog';
import { StealthDialog } from './StealthDialog';
import { SystemSettingsModal } from './SystemSettingsModal';
import { PortalDialog } from '../tools/PortalDialog';
import { CodeHistoryDialog } from '../tools/CodeHistoryDialog';
import { useIsAdmin } from '../../state/user-store';

/** Renders whichever app-level dialog is open. Mounted once in the root layout. */
export function DialogHost() {
  const isAdmin = useIsAdmin();
  const open = useModalStore((s) => s.open);
  const close = useModalStore((s) => s.close);
  const show = useModalStore((s) => s.show);
  // The Manage dialogs are opened from System Settings: Escape, close and Back return there (F-32).
  const back = () => show('system-settings');
  return (
    <>
      <ChatSettingsModal open={open === 'chat-settings'} onClose={close} />
      <SystemSettingsModal open={open === 'system-settings'} onClose={close} />
      <PreferencesDialog open={open === 'preferences'} onClose={back} onBack={back} />
      <SkillsDialog open={open === 'skills'} onClose={back} onBack={back} />
      <PersonasDialog open={open === 'personas'} onClose={back} onBack={back} />
      {/* Admin-only dialogs are not mounted for a user, so a stray show('models') cannot open them. */}
      {isAdmin ? (
        <>
          <AgentConfigDialog open={open === 'agent-config'} onClose={back} onBack={back} />
          <ModelsDialog open={open === 'models'} onClose={back} onBack={back} />
          <StealthDialog open={open === 'stealth'} onClose={back} onBack={back} />
          <PortalDialog open={open === 'portal'} onClose={close} />
        </>
      ) : null}
      <CodeHistoryDialog open={open === 'code-history'} onClose={close} />
    </>
  );
}
