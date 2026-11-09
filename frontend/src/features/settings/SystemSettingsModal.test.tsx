import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { SystemSettingsModal } from './SystemSettingsModal';
import { settingsApi } from '../../api/settings';

const system = {
  code_runner_timeout: 30,
  code_runner_memory_limit: '512M',
  code_runner_cpu_limit: '1.0',
  code_runner_max_output_size: 65536,
};

function mockSystem(extra: Record<string, unknown> = {}) {
  vi.spyOn(settingsApi, 'getSystem').mockResolvedValue({ ...system, ...extra });
  vi.spyOn(settingsApi, 'version').mockResolvedValue({ version: '1.0.0' });
}

describe('SystemSettingsModal code runner timeout', () => {
  afterEach(() => vi.restoreAllMocks());

  it('caps the timeout input at the maximum the API reports', async () => {
    mockSystem({ code_runner_max_timeout: 120 });
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    const input = (await screen.findByLabelText('Timeout (seconds)')) as HTMLInputElement;
    expect(input.max).toBe('120');
    expect(input.min).toBe('1');
  });

  it('has no max attribute when the API does not report one', async () => {
    mockSystem();
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    const input = (await screen.findByLabelText('Timeout (seconds)')) as HTMLInputElement;
    expect(input.getAttribute('max')).toBeNull();
  });

  it('does not send the read-only maximum back when saving', async () => {
    mockSystem({ code_runner_max_timeout: 120 });
    const save = vi.spyOn(settingsApi, 'saveCodeRunner').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<SystemSettingsModal open onClose={() => undefined} />);
    await screen.findByLabelText('Timeout (seconds)');
    fireEvent.click(screen.getByRole('button', { name: 'Save code runner settings' }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    const body = save.mock.calls[0]?.[0];
    expect(body).toEqual(system);
    expect(Object.keys(body ?? {})).not.toContain('code_runner_max_timeout');
  });
});
