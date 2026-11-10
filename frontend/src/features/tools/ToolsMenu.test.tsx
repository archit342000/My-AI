import { createRef } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { ADMIN, USER, signInAs } from '../../test/roles';
import { ToolsMenu } from './ToolsMenu';

function openMenu() {
  renderWithProviders(<ToolsMenu />);
  fireEvent.click(screen.getByRole('button', { name: 'AI tools' }));
}

describe('ToolsMenu by role', () => {
  it('a user has no Git Agent toggle and no browser portal button, but keeps the other tools', () => {
    signInAs(USER);
    openMenu();
    expect(screen.queryByText('Git Agent')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Open browser portal' })).toBeNull();
    for (const label of ['Research Agent', 'Browsing Agent', 'Code Execution']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByRole('button', { name: 'Code execution history' })).toBeInTheDocument();
  });

  it('the admin has the Git Agent toggle and the browser portal button', () => {
    signInAs(ADMIN);
    openMenu();
    expect(screen.getByText('Git Agent')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open browser portal' })).toBeInTheDocument();
  });
});

describe('ToolsMenu placement', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  /** The wrench sits near the bottom; the composer box around it starts higher. */
  function stubLayout() {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
      this: HTMLElement,
    ) {
      const box = this.id === 'composer-box';
      return (
        box
          ? { left: 10, top: 700, width: 370, height: 90, right: 380, bottom: 790 }
          : { left: 60, top: 740, width: 40, height: 40, right: 100, bottom: 780 }
      ) as DOMRect;
    });
  }

  function renderMenu() {
    const sheetRef = createRef<HTMLDivElement>();
    renderWithProviders(
      <div id="composer-box" ref={sheetRef}>
        <ToolsMenu sheetAnchorRef={sheetRef} />
      </div>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'AI tools' }));
    return screen.getByRole('dialog', { name: 'AI tools' });
  }

  it('on a wide screen the panel sits 8px above the wrench, whatever its height', () => {
    signInAs(USER);
    stubLayout();
    const panel = renderMenu();
    expect(panel.style.bottom).toBe(`${window.innerHeight - 740 + 8}px`);
    expect(panel.style.top).toBe('');
    expect(panel.style.width).toBe('320px');
  });

  it('on a phone it is a sheet on top of the composer box, as wide as the screen less 8px a side', () => {
    signInAs(USER);
    stubLayout();
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
    );
    const panel = renderMenu();
    expect(panel.style.bottom).toBe(`${window.innerHeight - 700 + 8}px`);
    expect(panel.style.width).toBe(`${window.innerWidth - 16}px`);
    expect(panel.style.left).toBe('8px');
  });

  it('Escape closes it and returns focus to the wrench', () => {
    signInAs(USER);
    stubLayout();
    renderMenu();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(document.querySelector('.ui-popover')).toBeNull();
    expect(document.activeElement?.id).toBe('tools-button');
  });
});
