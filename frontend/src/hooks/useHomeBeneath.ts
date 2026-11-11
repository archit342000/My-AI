import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { isPhoneWidth } from '../lib/breakpoints';

/**
 * On a phone, Back only leaves the app from Home (rule book Part 6). When the app is opened straight
 * on another page (a link to a chat), Home is put beneath it once, so Back goes there first.
 */
export function useHomeBeneath(): void {
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => {
    // The router numbers the entries it makes: 0 is the page the app was opened on.
    const opening = (window.history.state as { idx?: number } | null)?.idx === 0;
    if (!opening || !isPhoneWidth() || location.pathname === '/') return;
    const here = `${location.pathname}${location.search}${location.hash}`;
    void navigate('/', { replace: true });
    void navigate(here);
    // Once, on opening the app: later moves are ordinary history.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
