/** Zoom steps of the bigger view. */
export const VIEWER_ZOOM_STEPS = [0.5, 0.75, 1, 1.5, 2, 3] as const;
export const VIEWER_ZOOM_MIN = 0.5;
export const VIEWER_ZOOM_MAX = 3;

/** The next zoom step up or down from `zoom`, staying inside the range. */
export function stepZoom(zoom: number, direction: 1 | -1): number {
  const steps = VIEWER_ZOOM_STEPS;
  const index = steps.findIndex((step) => step >= zoom);
  const at = index === -1 ? steps.length - 1 : index;
  return steps[Math.min(steps.length - 1, Math.max(0, at + direction))] ?? zoom;
}
