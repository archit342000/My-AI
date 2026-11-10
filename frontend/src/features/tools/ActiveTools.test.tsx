import { act, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import { useSettingsStore } from '../../state/settings-store';
import { renderWithProviders } from '../../test/render';
import { ADMIN, USER, signInAs } from '../../test/roles';
import { ActiveTools } from './ActiveTools';

const ALL_OFF = {
  researchMode: false,
  fileSystemMode: false,
  browsingMode: false,
  gitMode: false,
  codeExecutionMode: false,
};

afterEach(() => act(() => useSettingsStore.setState({ modes: ALL_OFF })));

describe('ActiveTools', () => {
  it('shows nothing while every tool is off', () => {
    signInAs(ADMIN);
    act(() => useSettingsStore.setState({ modes: ALL_OFF }));
    const { container } = renderWithProviders(<ActiveTools />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows a chip per tool that is on, and its remove button switches the tool off', async () => {
    signInAs(ADMIN);
    act(() =>
      useSettingsStore.setState({
        modes: { ...ALL_OFF, codeExecutionMode: true, researchMode: true },
      }),
    );
    renderWithProviders(<ActiveTools />);
    const group = screen.getByRole('group', { name: 'Tools that are on' });
    expect(group).toHaveTextContent('Research');
    expect(group).toHaveTextContent('Code');
    await userEvent.click(screen.getByRole('button', { name: 'Switch off Code' }));
    expect(useSettingsStore.getState().modes.codeExecutionMode).toBe(false);
    expect(group).not.toHaveTextContent('Code');
  });

  it('never shows Git to someone who is not the admin', () => {
    signInAs(USER);
    act(() => useSettingsStore.setState({ modes: { ...ALL_OFF, gitMode: true } }));
    const { container } = renderWithProviders(<ActiveTools />);
    expect(container).toBeEmptyDOMElement();
  });
});
