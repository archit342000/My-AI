import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { SpeedChart } from './SpeedChart';

describe('SpeedChart', () => {
  it('draws one dot per turn and labels the extremes', () => {
    const { container } = render(
      <SpeedChart
        points={[
          { contextTokens: 1100, decodeTps: 50 },
          { contextTokens: 4200, decodeTps: 25 },
        ]}
      />,
    );
    expect(container.querySelectorAll('.speed-chart__dot')).toHaveLength(2);
    expect(container.querySelector('.speed-chart__line')).not.toBeNull();
    const labels = Array.from(container.querySelectorAll('.speed-chart__label')).map(
      (t) => t.textContent,
    );
    expect(labels).toEqual(['1,100 tokens', '4,200 tokens', '50.0 tok/s', '25.0 tok/s']);
  });

  it('draws only the axes without points', () => {
    const { container } = render(<SpeedChart points={[]} />);
    expect(container.querySelectorAll('.speed-chart__dot')).toHaveLength(0);
    expect(container.querySelectorAll('.speed-chart__label')).toHaveLength(0);
    expect(container.querySelectorAll('.speed-chart__axis')).toHaveLength(2);
  });
});
