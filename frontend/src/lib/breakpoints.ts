/**
 * The four screen sizes (rule book 5.1). A phone is under 600 wide; a tablet 600 to 1023;
 * a computer 1024 to 1599; very wide from 1600.
 */
export const PHONE_MAX_WIDTH = 599;
export const TABLET_MAX_WIDTH = 1023;

export const PHONE_QUERY = `(max-width: ${PHONE_MAX_WIDTH}px)`;
export const TABLET_QUERY = `(min-width: ${PHONE_MAX_WIDTH + 1}px) and (max-width: ${TABLET_MAX_WIDTH}px)`;

/** True on a phone-width window. */
export function isPhoneWidth(width: number = window.innerWidth): boolean {
  return width <= PHONE_MAX_WIDTH;
}
