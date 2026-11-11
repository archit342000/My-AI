import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Checkbox } from './Checkbox';

describe('Checkbox', () => {
  it('reports the opposite state when pressed, by pointer and by Space', async () => {
    const onChange = vi.fn();
    render(
      <Checkbox checked={false} onChange={onChange}>
        Remember me
      </Checkbox>,
    );
    const box = screen.getByRole('checkbox', { name: 'Remember me' });
    expect(box).toHaveAttribute('aria-checked', 'false');
    await userEvent.click(box);
    box.focus();
    await userEvent.keyboard(' ');
    expect(onChange.mock.calls).toEqual([[true], [true]]);
  });

  it('a mixed box becomes ticked, a ticked one clears, and a disabled one does nothing', async () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <Checkbox checked="mixed" onChange={onChange}>
        All
      </Checkbox>,
    );
    await userEvent.click(screen.getByRole('checkbox'));
    rerender(
      <Checkbox checked onChange={onChange}>
        All
      </Checkbox>,
    );
    await userEvent.click(screen.getByRole('checkbox'));
    rerender(
      <Checkbox checked onChange={onChange} disabled>
        All
      </Checkbox>,
    );
    await userEvent.click(screen.getByRole('checkbox'));
    expect(onChange.mock.calls).toEqual([[true], [false]]);
  });
});
