import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { Icon } from '../../components/icons/Icon';
import { Button } from '../../components/ui/Button';
import { TickRule } from '../../components/ui/TickRule';
import { pushModal } from '../../lib/modal-stack';
import { resetSaveLight } from '../../lib/save-light';
import { useIsAdmin } from '../../state/user-store';
import { SavedLight } from './SavedLight';
import { AgentsSection } from './sections/AgentsSection';
import { ChatSection } from './sections/ChatSection';
import { MemorySection } from './sections/MemorySection';
import { ModelsSection } from './sections/ModelsSection';
import { PersonasSection } from './sections/PersonasSection';
import { SkillsSection } from './sections/SkillsSection';
import { SystemSection } from './sections/SystemSection';
import {
  SETTINGS_SECTIONS,
  searchWithSection,
  sectionFromSearch,
  type SettingsSectionId,
} from './settings-nav';

const SECTION: Record<SettingsSectionId, () => React.ReactNode> = {
  chat: () => <ChatSection />,
  models: () => <ModelsSection />,
  personas: () => <PersonasSection />,
  skills: () => <SkillsSection />,
  memory: () => <MemorySection />,
  agents: () => <AgentsSection />,
  system: () => <SystemSection />,
};

/**
 * Settings: a full page over the content panel, with Back. A list of its parts on the left (a row of
 * tabs on a phone) and every part in one scrolling column. Settings are kept the moment they change;
 * the light in the header says so. Only a new or edited list item has a Save button.
 */
export function SettingsPage() {
  const isAdmin = useIsAdmin();
  const navigate = useNavigate();
  const location = useLocation();
  const asked = sectionFromSearch(location.search) ?? 'chat';
  // Agent, model and browser settings are process-wide: the server refuses them for anyone but the admin.
  const sections = SETTINGS_SECTIONS.filter((s) => isAdmin || !s.admin);
  const wanted = sections.some((s) => s.id === asked) ? asked : 'chat';
  const [current, setCurrent] = useState<SettingsSectionId>(wanted);
  const content = useRef<HTMLDivElement>(null);
  const page = useRef<HTMLDivElement>(null);
  const nav = useRef<HTMLElement>(null);
  // Where a jump to an asked-for part landed: while the column rests there, that part keeps the
  // highlight (the last part is too short to reach the top by itself). Null once the person scrolls.
  const landed = useRef<number | null>(null);

  const close = () => {
    const opened = Boolean((location.state as { settingsOpened?: boolean } | null)?.settingsOpened);
    // Back over the step that opened the page; a page reached by its address just drops the value.
    if (opened) navigate(-1);
    else
      navigate(
        { pathname: location.pathname, search: searchWithSection(location.search, null) },
        { replace: true },
      );
  };
  const closeRef = useRef(close);
  closeRef.current = close;

  useEffect(() => {
    resetSaveLight();
    // Focus moves into the page (so Tab starts at Back) without ringing a button nobody pressed.
    page.current?.focus();
    // Escape leaves the page, after anything open on top of it has closed.
    return pushModal(() => closeRef.current());
  }, []);

  // Bring the part the address names into view (on opening, and when the list or a link asks for one).
  useEffect(() => {
    const target = content.current?.querySelector<HTMLElement>(`[data-section="${wanted}"]`);
    if (!target) return undefined;
    setCurrent(wanted);
    const jump = () => {
      target.scrollIntoView?.({ block: 'start' });
      landed.current = content.current?.scrollTop ?? null;
    };
    jump();
    // The parts fill in as their data arrives, which moves everything below them: until the person
    // scrolls, keep the part that was asked for in place.
    const column = content.current?.firstElementChild;
    if (!column || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(() => {
      if (landed.current !== null) jump();
    });
    observer.observe(column);
    return () => observer.disconnect();
  }, [wanted]);

  // The list follows the scrolling: the part nearest the top of the column is the current one.
  function onScroll() {
    const box = content.current;
    if (!box) return;
    if (landed.current !== null && Math.abs(box.scrollTop - landed.current) < 4) return;
    landed.current = null;
    const top = box.getBoundingClientRect().top;
    const parts = Array.from(box.querySelectorAll<HTMLElement>('[data-section]'));
    let nearest: SettingsSectionId | null = null;
    for (const el of parts) {
      if (el.getBoundingClientRect().top - top <= 80)
        nearest = el.dataset.section as SettingsSectionId;
    }
    // At the very end the last part is the one being read, however short it is.
    if (box.scrollTop + box.clientHeight >= box.scrollHeight - 2) {
      nearest =
        (parts[parts.length - 1]?.dataset.section as SettingsSectionId | undefined) ?? nearest;
    }
    if (nearest && nearest !== current) setCurrent(nearest);
  }

  // On a phone the list is a row of tabs that scrolls sideways: keep the current one in view.
  useEffect(() => {
    nav.current
      ?.querySelector('[aria-current="true"]')
      ?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
  }, [current]);

  function go(id: SettingsSectionId) {
    if (id === wanted) {
      // Already the one in the address: scroll back to it all the same.
      content.current
        ?.querySelector<HTMLElement>(`[data-section="${id}"]`)
        ?.scrollIntoView?.({ block: 'start' });
      landed.current = content.current?.scrollTop ?? null;
      setCurrent(id);
      return;
    }
    navigate(
      { pathname: location.pathname, search: searchWithSection(location.search, id) },
      { replace: true, state: location.state },
    );
  }

  return (
    <div ref={page} className="setpage" role="region" aria-label="Settings" tabIndex={-1}>
      <header className="set-head">
        <Button variant="ghost" className="set-head__back" onClick={close}>
          <Icon name="chevron-left" size={18} />
          Back
        </Button>
        <h1 className="set-head__title">Settings</h1>
        <SavedLight />
      </header>
      <TickRule className="set-rule" />
      <div className="set-body">
        <nav ref={nav} className="set-nav" aria-label="Settings sections">
          {sections.map((s) => (
            <button
              key={s.id}
              type="button"
              className="set-nav__item"
              aria-current={current === s.id ? 'true' : undefined}
              onClick={() => go(s.id)}
            >
              <Icon name={s.icon} size={18} />
              <span>{s.label}</span>
            </button>
          ))}
        </nav>
        <div ref={content} className="set-content" onScroll={onScroll}>
          <div className="set-col">
            {sections.map((s) => (
              <div key={s.id}>{SECTION[s.id]()}</div>
            ))}
            <p className="ui-hint set-foot">
              Changes are kept straight away. Only a new or edited list item needs Save.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
