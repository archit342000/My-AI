import { beforeEach, describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useIsAdmin, useUserStore } from './user-store';

describe('user store', () => {
  beforeEach(() => useUserStore.setState({ user: null, sessionExpired: false }));

  it('is not an admin while the user is unknown', () => {
    expect(renderHook(() => useIsAdmin()).result.current).toBe(false);
  });

  it('is an admin only for the admin role', () => {
    const { result } = renderHook(() => useIsAdmin());
    act(() => useUserStore.setState({ user: { id: 'a', email: 'a@x', role: 'admin' } }));
    expect(result.current).toBe(true);
    act(() => useUserStore.setState({ user: { id: 'u', email: 'u@x', role: 'user' } }));
    expect(result.current).toBe(false);
  });

  it('records an expired session', () => {
    useUserStore.getState().setSessionExpired(true);
    expect(useUserStore.getState().sessionExpired).toBe(true);
  });
});
