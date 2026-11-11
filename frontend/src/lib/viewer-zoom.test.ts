import { describe, expect, it } from 'vitest';
import { stepZoom, VIEWER_ZOOM_MAX, VIEWER_ZOOM_MIN } from './viewer-zoom';

describe('stepZoom', () => {
  it('moves one step up or down', () => {
    expect(stepZoom(1, 1)).toBe(1.5);
    expect(stepZoom(1, -1)).toBe(0.75);
  });

  it('stops at both ends', () => {
    expect(stepZoom(VIEWER_ZOOM_MAX, 1)).toBe(VIEWER_ZOOM_MAX);
    expect(stepZoom(VIEWER_ZOOM_MIN, -1)).toBe(VIEWER_ZOOM_MIN);
    expect(stepZoom(10, 1)).toBe(VIEWER_ZOOM_MAX);
  });
});
