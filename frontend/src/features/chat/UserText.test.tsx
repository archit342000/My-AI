import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FOLD_CHARS } from '../../lib/user-text';
import { UserText } from './UserText';

describe('UserText', () => {
  it('shows a short message whole, with no Read more', () => {
    render(<UserText text="Where should I look first?" />);
    expect(screen.getByText('Where should I look first?')).toBeInTheDocument();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('folds a long message until Read more, and folds it again on Show less', () => {
    const { container } = render(<UserText text={'word '.repeat(FOLD_CHARS)} />);
    const body = container.querySelector('.user-text__body');
    expect(body).toHaveClass('user-text__body--folded');
    const more = screen.getByRole('button', { name: 'Read more' });
    expect(more).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(more);
    expect(body).not.toHaveClass('user-text__body--folded');
    fireEvent.click(screen.getByRole('button', { name: 'Show less' }));
    expect(body).toHaveClass('user-text__body--folded');
  });

  it('highlights a leading skill name and keeps the rest as text', () => {
    const { container } = render(<UserText text="/summarise-paper the attached file" />);
    expect(container.querySelector('.skill-name')?.textContent).toBe('/summarise-paper');
    expect(screen.getByText('the attached file')).toBeInTheDocument();
  });
});
