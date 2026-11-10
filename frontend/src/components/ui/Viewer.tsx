import { useState, type ReactNode } from 'react';
import { Button, IconButton } from './Button';
import { stepZoom, VIEWER_ZOOM_MAX, VIEWER_ZOOM_MIN } from '../../lib/viewer-zoom';
import { Window } from './Window';

export interface ViewerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

/** The bigger view (rule book 7.11): a picture or a diagram in a window, with zoom. */
export function Viewer({ open, onClose, title, children }: ViewerProps) {
  const [zoom, setZoom] = useState(1);
  const percent = `${Math.round(zoom * 100)}%`;

  return (
    <Window
      open={open}
      onClose={onClose}
      title={title}
      status={
        <div className="ui-viewer__zoom" role="group" aria-label="Zoom">
          <IconButton
            icon="minus"
            size="sm"
            label="Zoom out"
            disabled={zoom <= VIEWER_ZOOM_MIN}
            onClick={() => setZoom((z) => stepZoom(z, -1))}
          />
          <span className="dat keep" aria-live="polite">
            {percent}
          </span>
          <IconButton
            icon="plus"
            size="sm"
            label="Zoom in"
            disabled={zoom >= VIEWER_ZOOM_MAX}
            onClick={() => setZoom((z) => stepZoom(z, 1))}
          />
          <Button variant="ghost" size="sm" disabled={zoom === 1} onClick={() => setZoom(1)}>
            Reset
          </Button>
        </div>
      }
    >
      <div className="ui-viewer__stage">
        <div className="ui-viewer__content" style={{ zoom }} /* dynamic-style */>
          {children}
        </div>
      </div>
    </Window>
  );
}
