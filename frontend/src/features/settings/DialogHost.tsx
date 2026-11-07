import { useModalStore } from '../../state/modal-store';
import { AgentConfigDialog } from './AgentConfigDialog';
import { ChatSettingsModal } from './ChatSettingsModal';
import { ModelsDialog } from './ModelsDialog';
import { PersonasDialog } from './PersonasDialog';
import { PreferencesDialog } from './PreferencesDialog';
import { SkillsDialog } from './SkillsDialog';
import { StealthDialog } from './StealthDialog';
import { SystemSettingsModal } from './SystemSettingsModal';

/** Renders whichever app-level dialog is open. Mounted once in the root layout. */
export function DialogHost() {
  const open = useModalStore((s) => s.open);
  const close = useModalStore((s) => s.close);
  return (
    <>
      <ChatSettingsModal open={open === 'chat-settings'} onClose={close} />
      <SystemSettingsModal open={open === 'system-settings'} onClose={close} />
      <PreferencesDialog open={open === 'preferences'} onClose={close} />
      <SkillsDialog open={open === 'skills'} onClose={close} />
      <PersonasDialog open={open === 'personas'} onClose={close} />
      <AgentConfigDialog open={open === 'agent-config'} onClose={close} />
      <ModelsDialog open={open === 'models'} onClose={close} />
      <StealthDialog open={open === 'stealth'} onClose={close} />
    </>
  );
}
