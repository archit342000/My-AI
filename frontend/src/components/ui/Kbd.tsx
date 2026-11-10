/** Keys on the keyboard, one box per key: `<Kbd keys={['Ctrl', 'K']} />`. */
export function Kbd({ keys }: { keys: string[] }) {
  return (
    <span className="ui-kbd-group">
      {keys.map((key) => (
        <kbd key={key} className="ui-kbd">
          {key}
        </kbd>
      ))}
    </span>
  );
}
