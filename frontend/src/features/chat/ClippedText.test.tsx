import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ClippedText } from './ClippedText';

describe('ClippedText', () => {
  it('shows short text whole, under an accessible group name', () => {
    render(<ClippedText text="short" label="Result" />);
    expect(screen.getByRole('group', { name: 'Result' }).textContent).toBe('short');
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('clips long text and toggles between Show more and Show less', () => {
    const { container } = render(<ClippedText text={'x'.repeat(3000)} label="Result" />);
    expect(container.querySelector('pre')?.textContent?.length).toBeLessThan(1600);
    fireEvent.click(screen.getByRole('button', { name: /Show more/ }));
    expect(container.querySelector('pre')?.textContent?.length).toBe(3000);
    fireEvent.click(screen.getByRole('button', { name: 'Show less' }));
    expect(container.querySelector('pre')?.textContent?.length).toBeLessThan(1600);
  });
});
