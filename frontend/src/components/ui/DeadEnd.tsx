import { useState, type ReactNode } from 'react';
import { OnSphere } from '../background/OnSphere';
import { useSphereDim } from '../../hooks/useSphereDim';
import { DottedDrawing, type DrawingName } from './DottedDrawing';

export interface DeadEndProps {
  drawing: DrawingName;
  /** What happened, in one line: "This chat no longer exists." */
  title: string;
  /** One or two short lines of help. */
  children?: ReactNode;
  /** One row of buttons: the way out first. */
  actions?: ReactNode;
  /** A technical message, kept behind "Show details" (never shown first). */
  details?: string;
}

/**
 * A dead end (rule book 7.13): the thing asked for is gone, or something broke. The screen is open,
 * so the sphere shows at full strength and the words sit on it: a dotted drawing, what happened, a
 * line of help and a way out. Error codes stay behind "Show details".
 */
export function DeadEnd({ drawing, title, children, actions, details }: DeadEndProps) {
  useSphereDim('open');
  const [open, setOpen] = useState(false);
  return (
    <div className="dead-end" role="alert">
      <OnSphere className="dead-end__words">
        <DottedDrawing name={drawing} />
        <h1 className="dead-end__title">{title}</h1>
        {children ? <p className="dead-end__text">{children}</p> : null}
        {actions ? <div className="dead-end__actions">{actions}</div> : null}
      </OnSphere>
      {details ? (
        <div className="dead-end__details">
          <button
            type="button"
            className="ui-button ui-button--link"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? 'Hide details' : 'Show details'}
          </button>
          {open ? <pre className="dead-end__pre">{details}</pre> : null}
        </div>
      ) : null}
    </div>
  );
}
