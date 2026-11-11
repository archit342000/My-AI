import { renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, useLocation } from 'react-router';
import { afterEach, describe, expect, it } from 'vitest';
import { useHomeBeneath } from './useHomeBeneath';

const setWidth = (value: number) =>
  Object.defineProperty(window, 'innerWidth', { configurable: true, value });

function open(path: string, idx: number) {
  window.history.replaceState({ idx }, '');
  const wrapper = ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
  );
  return renderHook(
    () => {
      useHomeBeneath();
      return useLocation();
    },
    { wrapper },
  );
}

describe('useHomeBeneath', () => {
  afterEach(() => {
    setWidth(1024);
    window.history.replaceState(null, '');
  });

  it('on a phone opened straight on a chat, keeps the chat on screen (Home goes beneath it)', () => {
    setWidth(390);
    const { result } = open('/chat/c1?x=1', 0);
    expect(`${result.current.pathname}${result.current.search}`).toBe('/chat/c1?x=1');
    // Two moves were made: to Home (replacing), then on to the chat.
    expect(result.current.key).not.toBe('default');
  });

  it('leaves history alone on a computer, on Home, and after the first page', () => {
    setWidth(1024);
    expect(open('/chat/c1', 0).result.current.key).toBe('default');
    setWidth(390);
    expect(open('/', 0).result.current.key).toBe('default');
    expect(open('/chat/c1', 2).result.current.key).toBe('default');
  });
});
