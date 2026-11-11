import { describe, expect, it } from 'vitest';
import { isPhoneWidth, PHONE_QUERY, TABLET_QUERY } from './breakpoints';

describe('breakpoints', () => {
  it('a phone is under 600 wide', () => {
    expect(isPhoneWidth(390)).toBe(true);
    expect(isPhoneWidth(599)).toBe(true);
    expect(isPhoneWidth(600)).toBe(false);
  });

  it('the media queries match the rule book sizes', () => {
    expect(PHONE_QUERY).toBe('(max-width: 599px)');
    expect(TABLET_QUERY).toBe('(min-width: 600px) and (max-width: 1023px)');
  });
});
