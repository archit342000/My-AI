import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Chip } from './Chip';
import { Kbd } from './Kbd';
import { StatusLight } from './StatusLight';
import { Tag } from './Tag';
import { TickRule } from './TickRule';

// The small display pieces: chip, tag, status light, tick rule, keys.

describe('Chip', () => {
  it('shows its words, a tint when asked, and a named remove button only when it can be removed', async () => {
    const onRemove = vi.fn();
    const { rerender } = render(<Chip>Web search</Chip>);
    expect(screen.getByText('Web search')).not.toHaveClass('ui-chip--tint');
    expect(screen.queryByRole('button')).toBeNull();
    rerender(
      <Chip tint removeLabel="Remove notes.md" onRemove={onRemove}>
        notes.md
      </Chip>,
    );
    expect(screen.getByText('notes.md')).toHaveClass('ui-chip--tint');
    await userEvent.click(screen.getByRole('button', { name: 'Remove notes.md' }));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });
});

describe('StatusLight', () => {
  it('always carries its word, and marks tone and busy on the light', () => {
    render(<StatusLight label="Thinking" tone="warn" busy />);
    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('Thinking');
    expect(status.querySelector('.led')).toHaveClass('warn', 'busy');
  });
});

describe('Tag, TickRule and Kbd', () => {
  it('render their content; the rule is hidden from screen readers', () => {
    const { container } = render(
      <>
        <Tag>Python</Tag>
        <TickRule />
        <Kbd keys={['Ctrl', 'K']} />
      </>,
    );
    expect(screen.getByText('Python')).toHaveClass('ui-tag');
    expect(container.querySelector('.ticks')).toHaveAttribute('aria-hidden', 'true');
    expect([...container.querySelectorAll('kbd')].map((k) => k.textContent)).toEqual(['Ctrl', 'K']);
  });
});
