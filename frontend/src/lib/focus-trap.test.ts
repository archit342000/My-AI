import { afterEach, describe, expect, it } from 'vitest';
import { focusableWithin, trapFocus } from './focus-trap';

function setup() {
  const outside = document.createElement('button');
  outside.textContent = 'outside';
  const container = document.createElement('div');
  container.innerHTML = '<button id="a">a</button><button id="b">b</button><button id="c">c</button>';
  document.body.append(outside, container);
  outside.focus();
  return { outside, container };
}

function press(key: string, shiftKey = false) {
  const event = new KeyboardEvent('keydown', { key, shiftKey, bubbles: true, cancelable: true });
  document.dispatchEvent(event);
  return event;
}

afterEach(() => {
  document.body.innerHTML = '';
});

describe('focusableWithin', () => {
  it('lists interactive descendants in DOM order and skips disabled ones', () => {
    const { container } = setup();
    container.querySelector<HTMLButtonElement>('#b')!.disabled = true;
    expect(focusableWithin(container).map((el) => el.id)).toEqual(['a', 'c']);
  });
});

describe('trapFocus', () => {
  it('focuses the first control on activation', () => {
    const { container } = setup();
    const release = trapFocus(container);
    expect(document.activeElement?.id).toBe('a');
    release();
  });

  it('wraps Tab from the last control to the first', () => {
    const { container } = setup();
    const release = trapFocus(container);
    container.querySelector<HTMLElement>('#c')!.focus();
    const event = press('Tab');
    expect(event.defaultPrevented).toBe(true);
    expect(document.activeElement?.id).toBe('a');
    release();
  });

  it('wraps Shift+Tab from the first control to the last', () => {
    const { container } = setup();
    const release = trapFocus(container);
    press('Tab', true);
    expect(document.activeElement?.id).toBe('c');
    release();
  });

  it('pulls focus back in when it has escaped the container', () => {
    const { container, outside } = setup();
    const release = trapFocus(container);
    outside.focus();
    press('Tab');
    expect(document.activeElement?.id).toBe('a');
    release();
  });

  it('restores the previously focused element on release and stops trapping', () => {
    const { container, outside } = setup();
    const release = trapFocus(container);
    release();
    expect(document.activeElement).toBe(outside);
    const event = press('Tab');
    expect(event.defaultPrevented).toBe(false);
  });
});
