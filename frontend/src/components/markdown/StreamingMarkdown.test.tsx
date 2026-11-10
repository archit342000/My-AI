import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { StreamingMarkdown } from './StreamingMarkdown';

describe('StreamingMarkdown', () => {
  it('leaves the DOM of finished blocks untouched while the last block grows', () => {
    const { container, rerender } = render(
      <StreamingMarkdown text={'First paragraph.\n\nSecond'} />,
    );
    const first = container.querySelector('p');
    expect(first?.textContent).toBe('First paragraph.');
    rerender(<StreamingMarkdown text={'First paragraph.\n\nSecond paragraph so far'} />);
    expect(container.querySelectorAll('p')[0]).toBe(first);
    expect(container.textContent).toContain('Second paragraph so far');
    rerender(<StreamingMarkdown text={'First paragraph.\n\nSecond paragraph so far.\n\nThird'} />);
    expect(container.querySelectorAll('p')[0]).toBe(first);
    expect(container.querySelectorAll('p').length).toBe(3);
  });

  it('hides a think block that spans a blank line instead of showing half of it', () => {
    const { container } = render(
      <StreamingMarkdown text={'<think>first part\n\nsecond part</think>The answer.'} />,
    );
    expect(container.textContent?.trim()).toBe('The answer.');
  });

  it('renders a code block with its blank line as one block', () => {
    const { container } = render(<StreamingMarkdown text={'```\na\n\nb\n```'} />);
    expect(container.querySelectorAll('pre')).toHaveLength(1);
  });
});
