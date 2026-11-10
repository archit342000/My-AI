import { renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useSphereDim } from './useSphereDim';

describe('useSphereDim', () => {
  it('publishes the strength on <html>, follows changes and falls back to reading on unmount', () => {
    const { rerender, unmount } = renderHook(
      ({ dim }: { dim: 'open' | 'read' }) => useSphereDim(dim),
      {
        initialProps: { dim: 'open' as 'open' | 'read' },
      },
    );
    expect(document.documentElement.dataset.dim).toBe('open');
    rerender({ dim: 'read' });
    expect(document.documentElement.dataset.dim).toBe('read');
    rerender({ dim: 'open' });
    unmount();
    expect(document.documentElement.dataset.dim).toBe('read');
  });
});
