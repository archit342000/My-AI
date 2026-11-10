import { Icon } from '../../components/icons/Icon';
import { IconButton } from '../../components/ui/Button';
import type { SearchHit } from './file-search';

/** The search box above the file list. */
export function FileSearchBox({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="fb-search">
      <Icon name="search" size={16} className="fb-search__icon" />
      <input
        type="search"
        className="ui-input fb-search__input"
        aria-label="Search files"
        placeholder="Search files"
        autoComplete="off"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {value ? (
        <IconButton
          icon="close"
          size="sm"
          className="fb-search__clear"
          label="Clear the search"
          tooltip={false}
          onClick={() => onChange('')}
        />
      ) : null}
    </div>
  );
}

/** What a search found: each file once, with the first matching line of its text when there is one. */
export function FileSearchResults({
  hits,
  selected,
  onOpen,
}: {
  hits: SearchHit[];
  selected: string | null;
  onOpen: (id: string) => void;
}) {
  return (
    <ul className="fb-files fb-results" aria-label="Search results">
      {hits.map(({ artifact, path, line }) => (
        <li key={artifact.id}>
          <button
            type="button"
            className="fb-row__main artifact-item"
            aria-current={selected === artifact.id}
            title={path}
            onClick={() => onOpen(artifact.id)}
          >
            <Icon name="file-text" size={16} />
            <span className="fb-row__name">{path}</span>
          </button>
          {line ? (
            <p className="fb-snip">
              <span className="dat keep">Line {line.number}</span> {line.text}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
