import { describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { modelsApi } from '../../api/settings';
import { useModelDisplayName } from './useModelDisplayName';

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('useModelDisplayName', () => {
  it('returns the raw id until the config is loaded, then the display name', async () => {
    vi.spyOn(modelsApi, 'config').mockResolvedValue({
      general: { text: 'Google/Gemma4-26B-A4B-it' },
    });
    const { result } = renderHook(() => useModelDisplayName(), { wrapper });
    expect(result.current('Google/Gemma4-26B-A4B-it')).toBe('Google/Gemma4-26B-A4B-it');
    await waitFor(() =>
      expect(result.current('Google/Gemma4-26B-A4B-it')).toBe('General Text (Gemma4-26B-A4B-it)'),
    );
    expect(result.current('unknown/model')).toBe('unknown/model');
  });
});
