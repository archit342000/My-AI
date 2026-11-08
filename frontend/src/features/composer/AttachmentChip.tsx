import { useEffect, useState, type CSSProperties } from 'react';
import { IconButton } from '../../components/ui/Button';
import { Tooltip } from '../../components/ui/Tooltip';
import { Icon } from '../../components/icons/Icon';
import { cx } from '../../lib/cx';
import { attachmentStatusLabel, isImageType, type Attachment } from './attachments';

export interface AttachmentChipProps {
  item: Attachment;
  onRemove: () => void;
  onRetry: () => void;
}

/** One staged file: thumbnail or icon, truncated name with the full name on hover, and its state. */
export function AttachmentChip({ item, onRemove, onRetry }: AttachmentChipProps) {
  const thumbnail = useObjectUrl(isImageType(item.mimeType) ? item.file : null);
  const label = attachmentStatusLabel(item);
  return (
    <div
      className={cx('composer-chip', statusModifier(item.status))}
      data-status={item.status}
    >
      {thumbnail ? (
        <img className="composer-chip__thumb" src={thumbnail} alt="" />
      ) : (
        <span className="composer-chip__icon" aria-hidden="true">
          <Icon name={isImageType(item.mimeType) ? 'file' : 'file-text'} size={16} />
        </span>
      )}
      <span className="composer-chip__body">
        <Tooltip content={item.name}>
          <span className="composer-chip__name">{item.name}</span>
        </Tooltip>
        <span className="composer-chip__status" role="status">
          {item.status === 'processing' ? (
            <span className="ui-spinner composer-chip__spinner" aria-hidden="true" />
          ) : null}
          {label}
        </span>
        {item.status === 'uploading' ? (
          <span className="composer-chip__progress" aria-hidden="true">
            <span
              className="composer-chip__progress-fill"
              style={{ '--progress': item.progress } as CSSProperties} // dynamic-style
            />
          </span>
        ) : null}
      </span>
      {item.status === 'ready' ? (
        <span className="composer-chip__ok" aria-hidden="true">
          <Icon name="check" size={14} strokeWidth={2.5} />
        </span>
      ) : null}
      {item.status === 'error' ? (
        <IconButton
          icon="refresh-cw"
          size="sm"
          label={`Retry ${item.name}`}
          onClick={onRetry}
        />
      ) : null}
      <IconButton icon="close" size="sm" label={`Remove ${item.name}`} onClick={onRemove} />
    </div>
  );
}

/** Modifier class for the chip's state (only error and ready are styled differently). */
function statusModifier(status: Attachment['status']): string | undefined {
  if (status === 'error') return 'composer-chip--error';
  if (status === 'ready') return 'composer-chip--ready';
  return undefined;
}

/** Object URL for a preview, revoked when the file changes or the chip unmounts. */
function useObjectUrl(file: File | null): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!file) return undefined;
    const next = URL.createObjectURL(file);
    setUrl(next);
    return () => {
      URL.revokeObjectURL(next);
      setUrl(null);
    };
  }, [file]);
  return url;
}
