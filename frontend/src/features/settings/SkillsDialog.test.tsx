import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { SkillsDialog } from './SkillsDialog';
import { skillsApi } from '../../api/settings';

const skill = { id: 's1', name: 'summarise', description: 'Short summary', instructions: 'Be brief' };

describe('SkillsDialog', () => {
  afterEach(() => vi.restoreAllMocks());

  it('lists skills as /name with description', async () => {
    vi.spyOn(skillsApi, 'list').mockResolvedValue([skill]);
    renderWithProviders(<SkillsDialog open onClose={() => undefined} />);
    expect(await screen.findByText('/summarise')).toBeTruthy();
    expect(screen.getByText('Short summary')).toBeTruthy();
  });

  it('shows the empty-state copy', async () => {
    vi.spyOn(skillsApi, 'list').mockResolvedValue([]);
    renderWithProviders(<SkillsDialog open onClose={() => undefined} />);
    expect(await screen.findByText(/No skills yet/)).toBeTruthy();
  });

  it('requires name, description and instructions before saving', async () => {
    vi.spyOn(skillsApi, 'list').mockResolvedValue([]);
    const create = vi.spyOn(skillsApi, 'create');
    renderWithProviders(<SkillsDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: /Add/ }));
    // Save stays disabled until name, description and instructions are all set.
    expect((screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement).disabled).toBe(true);
    expect(create).not.toHaveBeenCalled();
  });

  it('a missing description alone blocks the save (N7)', async () => {
    vi.spyOn(skillsApi, 'list').mockResolvedValue([]);
    const create = vi.spyOn(skillsApi, 'create');
    renderWithProviders(<SkillsDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: /Add/ }));
    fireEvent.change(screen.getByRole('textbox', { name: /Name/ }), { target: { value: 'review' } });
    fireEvent.change(screen.getByRole('textbox', { name: /Instructions/ }), { target: { value: 'check code' } });
    expect((screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement).disabled).toBe(true);
    expect(create).not.toHaveBeenCalled();
  });

  it('creates a skill with trimmed fields', async () => {
    vi.spyOn(skillsApi, 'list').mockResolvedValue([]);
    const create = vi.spyOn(skillsApi, 'create').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<SkillsDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: /Add/ }));
    fireEvent.change(screen.getByRole('textbox', { name: /Name/ }), { target: { value: ' review ' } });
    fireEvent.change(screen.getByRole('textbox', { name: /Description/ }), { target: { value: ' Reviews code ' } });
    fireEvent.change(screen.getByRole('textbox', { name: /Instructions/ }), { target: { value: ' check code ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(create).toHaveBeenCalledWith({ name: 'review', description: 'Reviews code', instructions: 'check code' }));
  });

  it('editing calls update with the id and surfaces a server failure', async () => {
    vi.spyOn(skillsApi, 'list').mockResolvedValue([skill]);
    const update = vi.spyOn(skillsApi, 'update').mockRejectedValue(new Error('name taken'));
    renderWithProviders(<SkillsDialog open onClose={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Edit /summarise' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('name taken');
    expect(update).toHaveBeenCalledWith('s1', expect.objectContaining({ name: 'summarise' }));
  });
});
