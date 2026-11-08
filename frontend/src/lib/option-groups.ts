/** Minimal option shape that can be grouped. */
export interface GroupableOption {
  value: string;
  label: string;
  group?: string;
  disabled?: boolean;
}

export type NumberedOption<T extends GroupableOption> = T & {
  /** Position in the rendered order (see groupOptions). */
  index: number;
};

export interface OptionGroup<T extends GroupableOption> {
  name: string | null;
  options: Array<NumberedOption<T>>;
}

/**
 * Groups options by `group` (first-seen order). Ungrouped options come first. Every option gets an
 * `index` in rendered order, so keyboard focus can refer to it.
 */
export function groupOptions<T extends GroupableOption>(options: T[]): Array<OptionGroup<T>> {
  const ungrouped: OptionGroup<T> = { name: null, options: [] };
  const groups = new Map<string, OptionGroup<T>>();
  for (const option of options) {
    if (!option.group) {
      ungrouped.options.push(option as NumberedOption<T>);
      continue;
    }
    const group = groups.get(option.group) ?? { name: option.group, options: [] };
    groups.set(option.group, group);
    group.options.push(option as NumberedOption<T>);
  }
  const ordered = [ungrouped, ...groups.values()].filter((group) => group.options.length > 0);
  let index = 0;
  for (const group of ordered) {
    for (const option of group.options) option.index = index++;
  }
  return ordered;
}
