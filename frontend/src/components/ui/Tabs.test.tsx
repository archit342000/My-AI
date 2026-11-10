import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Tabs } from './Tabs';

const OPTIONS = [
  { value: 'network', label: 'Network', panelId: 'p-network' },
  { value: 'events', label: 'Events' },
  { value: 'app', label: 'App' },
];

describe('Tabs', () => {
  it('marks the current tab and is one stop in the Tab order', () => {
    render(<Tabs label="Log kind" value="events" onChange={vi.fn()} options={OPTIONS} />);
    expect(screen.getByRole('tablist', { name: 'Log kind' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Events' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Events' })).toHaveAttribute('tabindex', '0');
    expect(screen.getByRole('tab', { name: 'Network' })).toHaveAttribute('tabindex', '-1');
    expect(screen.getByRole('tab', { name: 'Network' })).toHaveAttribute(
      'aria-controls',
      'p-network',
    );
  });

  it('selects on click and with the arrow, Home and End keys, wrapping at the ends', async () => {
    const onChange = vi.fn();
    render(<Tabs label="Log kind" value="app" onChange={onChange} options={OPTIONS} />);
    await userEvent.click(screen.getByRole('tab', { name: 'Network' }));
    screen.getByRole('tab', { name: 'App' }).focus();
    await userEvent.keyboard('{ArrowRight}');
    screen.getByRole('tab', { name: 'App' }).focus();
    await userEvent.keyboard('{Home}');
    screen.getByRole('tab', { name: 'Network' }).focus();
    await userEvent.keyboard('{End}');
    expect(onChange.mock.calls).toEqual([['network'], ['network'], ['network'], ['app']]);
  });
});
