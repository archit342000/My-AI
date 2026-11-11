import { useState } from 'react';
import { Markdown } from '../../components/markdown/Markdown';
import { cx } from '../../lib/cx';
import { isLongMessage, splitSkill } from '../../lib/user-text';

/**
 * The text of a sent message: a leading skill name is highlighted, and a long message is folded
 * until "Read more" (rule book: detail waits until asked).
 */
export function UserText({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const { skill, rest } = splitSkill(text);
  const long = isLongMessage(text);
  return (
    <div className="user-text">
      <div className={cx('user-text__body', long && !open && 'user-text__body--folded')}>
        {skill ? <span className="skill-name">{skill}</span> : null}
        {rest ? <Markdown text={rest} className="message-text-wrapper" /> : null}
      </div>
      {long ? (
        <button
          type="button"
          className="ui-button ui-button--link user-text__more"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? 'Show less' : 'Read more'}
        </button>
      ) : null}
    </div>
  );
}
