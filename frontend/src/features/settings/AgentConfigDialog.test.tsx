import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { AgentConfigDialog } from './AgentConfigDialog';
import { settingsApi } from '../../api/settings';

const agents = {
  research: { max_tokens: 4096, thinking_budget: 1000, thinking_profile: 'general' },
};

describe('AgentConfigDialog footer', () => {
  afterEach(() => vi.restoreAllMocks());

  it('has Cancel then the primary Save changes in the footer, and Cancel closes the dialog', async () => {
    vi.spyOn(settingsApi, 'getAgents').mockResolvedValue(agents as never);
    const onClose = vi.fn();
    renderWithProviders(<AgentConfigDialog open onClose={onClose} />);
    await screen.findAllByLabelText('Max tokens');
    const footer = document.querySelector('.modal-footer') as HTMLElement;
    expect(Array.from(footer.querySelectorAll('button')).map((b) => b.textContent)).toEqual([
      'Cancel',
      'Save changes',
    ]);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('typed edits survive a refetch with different data while the dialog is open', async () => {
    const get = vi.spyOn(settingsApi, 'getAgents').mockResolvedValue(agents as never);
    const { client } = renderWithProviders(<AgentConfigDialog open onClose={() => undefined} />);
    const field = (await screen.findAllByLabelText('Max tokens'))[0] as HTMLInputElement;
    fireEvent.change(field, { target: { value: '9999' } });
    get.mockResolvedValue({
      research: { max_tokens: 2048, thinking_budget: 1000, thinking_profile: 'general' },
    } as never);
    await client.invalidateQueries({ queryKey: ['settings', 'agents'] });
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
    expect((screen.getAllByLabelText('Max tokens')[0] as HTMLInputElement).value).toBe('9999');
  });

  it('an untouched draft follows newer saved values when a refetch lands after opening', async () => {
    const get = vi.spyOn(settingsApi, 'getAgents').mockResolvedValue(agents as never);
    const { client } = renderWithProviders(<AgentConfigDialog open onClose={() => undefined} />);
    await screen.findAllByLabelText('Max tokens');
    get.mockResolvedValue({ research: { max_tokens: 2048, thinking_budget: 1000, thinking_profile: 'general' } } as never);
    await client.invalidateQueries({ queryKey: ['settings', 'agents'] });
    await waitFor(() => expect((screen.getAllByLabelText('Max tokens')[0] as HTMLInputElement).value).toBe('2048'));
    expect((screen.getByRole('button', { name: 'Save changes' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('Cancel discards unsaved edits: reopening shows the saved values and Save is disabled', async () => {
    vi.spyOn(settingsApi, 'getAgents').mockResolvedValue(agents as never);
    function Harness() {
      const [open, setOpen] = useState(true);
      return (
        <>
          <button onClick={() => setOpen(true)}>reopen</button>
          <AgentConfigDialog open={open} onClose={() => setOpen(false)} />
        </>
      );
    }
    renderWithProviders(<Harness />);
    const field = (await screen.findAllByLabelText('Max tokens'))[0] as HTMLInputElement;
    fireEvent.change(field, { target: { value: '9999' } });
    expect(
      (screen.getByRole('button', { name: 'Save changes' }) as HTMLButtonElement).disabled,
    ).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    fireEvent.click(screen.getByRole('button', { name: 'reopen' }));
    const again = (await screen.findAllByLabelText('Max tokens'))[0] as HTMLInputElement;
    expect(again.value).toBe('4096');
    expect(
      (screen.getByRole('button', { name: 'Save changes' }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });
});
