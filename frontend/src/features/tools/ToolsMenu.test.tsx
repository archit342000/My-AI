import { describe, expect, it } from 'vitest';
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
