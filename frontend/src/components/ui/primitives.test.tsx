import { useState } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Badge } from './Badge';
import { Button, IconButton } from './Button';
import { EmptyState } from './EmptyState';
import { Field, Input, Textarea } from './Field';
import { Menu, type MenuEntry } from './Menu';
import { RadioCards } from './RadioCards';
import { SegmentedControl } from './SegmentedControl';
import { Select, type SelectOption } from './Select';
import { Slider } from './Slider';
import { Toggle } from './Toggle';
import { Tooltip } from './Tooltip';
import { openPopoverCount } from './popover-stack';

describe('Button and IconButton', () => {
  it('applies the variant class and defaults to type=button', () => {
    render(<Button variant="danger">Delete</Button>);
    const button = screen.getByRole('button', { name: 'Delete' });
    expect(button).toHaveClass('ui-button', 'ui-button--danger');
    expect(button).toHaveAttribute('type', 'button');
  });

  it('loading disables the button and marks it busy', () => {
    render(<Button loading>Save</Button>);
    const button = screen.getByRole('button', { name: 'Save' });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
  });

  it('IconButton exposes its label as the accessible name', async () => {
    const onClick = vi.fn();
    render(<IconButton icon="close" label="Close dialog" tooltip={false} onClick={onClick} />);
    await userEvent.click(screen.getByRole('button', { name: 'Close dialog' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

describe('Tooltip', () => {
  it('shows the content on focus and hides on blur', async () => {
    render(
      <Tooltip content="Copy message">
        <button type="button">copy</button>
      </Tooltip>,
    );
    screen.getByRole('button', { name: 'copy' }).focus();
    expect(await screen.findByRole('tooltip', {}, { timeout: 1000 })).toHaveTextContent(
      'Copy message',
    );
    screen.getByRole('button', { name: 'copy' }).blur();
    await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull());
  });
});

const models: SelectOption[] = [
  { value: 'qwen', label: 'Qwen 3.5', group: 'Local', dot: 'success' },
  { value: 'llama', label: 'Llama 3', group: 'Local', dot: 'off' },
  { value: 'gpt', label: 'GPT Remote', group: 'Hosted' },
  { value: 'none', label: 'Disabled one', disabled: true },
];

function SelectHarness({ searchable = false }: { searchable?: boolean }) {
  const [value, setValue] = useState('qwen');
  return (
    <>
      <Select
        aria-label="Model"
        value={value}
        onChange={setValue}
        options={models}
        searchable={searchable}
      />
      <output data-testid="value">{value}</output>
    </>
  );
}

describe('Select', () => {
  it('opens a listbox with grouped options and selects with Enter', async () => {
    render(<SelectHarness />);
    const trigger = screen.getByRole('combobox', { name: 'Model' });
    expect(trigger).toHaveTextContent('Qwen 3.5');
    await userEvent.click(trigger);
    const listbox = screen.getByRole('listbox');
    expect(within(listbox).getByText('Hosted')).toBeInTheDocument();
    await userEvent.keyboard('{ArrowDown}{Enter}');
    expect(screen.getByTestId('value')).toHaveTextContent('llama');
    expect(trigger).toHaveFocus();
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('skips disabled options when moving and never selects them', async () => {
    render(<SelectHarness />);
    await userEvent.click(screen.getByRole('combobox', { name: 'Model' }));
    await userEvent.keyboard('{End}{Enter}');
    expect(screen.getByTestId('value')).toHaveTextContent('gpt');
    await userEvent.click(screen.getByRole('combobox', { name: 'Model' }));
    await userEvent.keyboard('{Home}{Enter}');
    expect(screen.getByTestId('value')).toHaveTextContent('qwen');
  });

  it('Escape closes the list and keeps focus on the trigger', async () => {
    render(<SelectHarness />);
    const trigger = screen.getByRole('combobox', { name: 'Model' });
    await userEvent.click(trigger);
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(trigger).toHaveFocus();
    expect(screen.getByTestId('value')).toHaveTextContent('qwen');
  });

  it('type-ahead moves the active option to the matching label', async () => {
    render(<SelectHarness />);
    const trigger = screen.getByRole('combobox', { name: 'Model' });
    await userEvent.click(trigger);
    await userEvent.keyboard('g');
    await userEvent.keyboard('{Enter}');
    expect(screen.getByTestId('value')).toHaveTextContent('gpt');
  });

  it('filters with the search field and chooses by click', async () => {
    render(<SelectHarness searchable />);
    await userEvent.click(screen.getByRole('combobox', { name: 'Model' }));
    const search = screen.getByRole('searchbox');
    expect(search).toHaveFocus();
    await userEvent.type(search, 'llama');
    expect(screen.queryByRole('option', { name: /Qwen/ })).toBeNull();
    await userEvent.click(screen.getByRole('option', { name: /Llama 3/ }));
    expect(screen.getByTestId('value')).toHaveTextContent('llama');
  });

  it('shows the empty text when the filter matches nothing', async () => {
    render(<SelectHarness searchable />);
    await userEvent.click(screen.getByRole('combobox', { name: 'Model' }));
    await userEvent.type(screen.getByRole('searchbox'), 'zzz');
    expect(screen.getByText('No matches')).toBeInTheDocument();
  });
});

function MenuHarness({
  onPick,
  extra = [] as MenuEntry[],
}: {
  onPick: (id: string) => void;
  extra?: MenuEntry[];
}) {
  const items: MenuEntry[] = [
    { id: 'rename', label: 'Rename', onSelect: () => onPick('rename') },
    { type: 'separator', id: 'sep' },
    { id: 'delete', label: 'Delete', danger: true, onSelect: () => onPick('delete') },
    ...extra,
  ];
  return (
    <Menu
      label="Chat actions"
      items={items}
      trigger={(props) => (
        <button type="button" {...props}>
          More
        </button>
      )}
    />
  );
}

describe('Menu', () => {
  it('opens, moves with arrow keys, chooses with Enter and returns focus to the trigger', async () => {
    const onPick = vi.fn();
    render(<MenuHarness onPick={onPick} />);
    const trigger = screen.getByRole('button', { name: 'More' });
    await userEvent.click(trigger);
    const first = screen.getByRole('menuitem', { name: 'Rename' });
    await waitFor(() => expect(first).toHaveFocus());
    await userEvent.keyboard('{ArrowDown}{Enter}');
    expect(onPick).toHaveBeenCalledWith('delete');
    expect(trigger).toHaveFocus();
    expect(screen.queryByRole('menu')).toBeNull();
  });

  it('renders separators and danger styling', async () => {
    render(<MenuHarness onPick={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    expect(screen.getByRole('separator')).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Delete' })).toHaveClass('ui-menu__item--danger');
  });

  it('Escape closes the menu', async () => {
    render(<MenuHarness onPick={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    await screen.findByRole('menu');
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).toBeNull();
    expect(openPopoverCount()).toBe(0);
  });

  it('a pointer down outside closes the menu without stealing focus', async () => {
    render(
      <>
        <button type="button">elsewhere</button>
        <MenuHarness onPick={vi.fn()} />
      </>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    await screen.findByRole('menu');
    fireEvent.pointerDown(screen.getByRole('button', { name: 'elsewhere' }));
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull());
  });

  it('submenu opens on ArrowRight and an item inside it is chosen', async () => {
    const onPick = vi.fn();
    render(
      <MenuHarness
        onPick={onPick}
        extra={[
          {
            type: 'submenu',
            id: 'move',
            label: 'Move to workspace',
            items: [{ id: 'ws-1', label: 'Work', onSelect: () => onPick('ws-1') }],
          },
        ]}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    const sub = await screen.findByRole('menuitem', { name: /Move to workspace/ });
    sub.focus();
    await userEvent.keyboard('{ArrowRight}');
    const work = await screen.findByRole('menuitem', { name: 'Work' });
    await waitFor(() => expect(work).toHaveFocus());
    await userEvent.keyboard('{Enter}');
    expect(onPick).toHaveBeenCalledWith('ws-1');
  });
});

describe('Toggle', () => {
  it('flips aria-checked and links the description', async () => {
    function Harness() {
      const [on, setOn] = useState(false);
      return (
        <Toggle
          checked={on}
          onChange={setOn}
          label="Vision"
          description="Send images to the model"
        />
      );
    }
    render(<Harness />);
    const toggle = screen.getByRole('switch', { name: 'Vision' });
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    expect(toggle).toHaveAccessibleDescription('Send images to the model');
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'true');
  });
});

describe('RadioCards and SegmentedControl', () => {
  it('RadioCards selects with arrow keys', async () => {
    const onChange = vi.fn();
    render(
      <RadioCards
        label="Stealth level"
        value="low"
        onChange={onChange}
        options={[
          { value: 'low', title: 'Minimal', description: 'Light' },
          { value: 'high', title: 'Full', description: 'Heavy' },
        ]}
      />,
    );
    screen.getByRole('radio', { name: /Minimal/ }).focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(onChange).toHaveBeenCalledWith('high');
  });

  it('SegmentedControl reports the clicked value', async () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl
        label="View"
        value="preview"
        onChange={onChange}
        options={[
          { value: 'preview', label: 'Preview' },
          { value: 'edit', label: 'Edit' },
        ]}
      />,
    );
    await userEvent.click(screen.getByRole('radio', { name: 'Edit' }));
    expect(onChange).toHaveBeenCalledWith('edit');
  });
});

describe('Slider', () => {
  const box = () =>
    screen.getByRole('spinbutton', { name: 'Max tokens value' }) as HTMLInputElement;
  const setup = (value = 16384, onChange = vi.fn()) => {
    render(
      <Slider
        label="Max tokens"
        value={value}
        onChange={onChange}
        min={256}
        max={32768}
        step={256}
        decimals={0}
      />,
    );
    return onChange;
  };

  it('accepts typing and commits on blur', () => {
    const onChange = setup();
    fireEvent.focus(box());
    fireEvent.change(box(), { target: { value: '5000' } });
    expect(onChange).not.toHaveBeenCalled(); // typing does not clamp or commit
    expect(box().value).toBe('5000');
    fireEvent.blur(box());
    expect(onChange).toHaveBeenLastCalledWith(5120); // rounded to the 256 step
  });

  it('can be cleared and retyped, and a cleared box restores the previous value on blur', () => {
    const onChange = setup(8192);
    fireEvent.focus(box());
    fireEvent.change(box(), { target: { value: '' } });
    expect(box().value).toBe('');
    fireEvent.blur(box());
    expect(onChange).not.toHaveBeenCalled();
    expect(box().value).toBe('8192');
  });

  it('clamps an out-of-range entry on blur', () => {
    const onChange = setup();
    fireEvent.focus(box());
    fireEvent.change(box(), { target: { value: '99999' } });
    fireEvent.blur(box());
    expect(onChange).toHaveBeenLastCalledWith(32768);
    fireEvent.focus(box());
    fireEvent.change(box(), { target: { value: '1' } });
    fireEvent.keyDown(box(), { key: 'Enter' });
    expect(onChange).toHaveBeenLastCalledWith(256);
  });

  it('Escape restores the value without committing (with real focus, so the blur it causes is real)', () => {
    const onChange = setup(4096);
    act(() => box().focus());
    fireEvent.change(box(), { target: { value: '777' } });
    fireEvent.keyDown(box(), { key: 'Escape' });
    expect(box().value).toBe('4096');
    expect(onChange).not.toHaveBeenCalled();
    expect(document.activeElement).not.toBe(box());
  });

  it('focusing and leaving the number box without typing does not change the value', () => {
    const onChange = setup(2050);
    fireEvent.focus(box());
    fireEvent.blur(box());
    expect(onChange).not.toHaveBeenCalled();
  });

  it('Enter commits once and leaves the box, so the next keystroke does not append to the old text', () => {
    const onChange = setup(2048);
    act(() => box().focus());
    fireEvent.change(box(), { target: { value: '3000' } });
    fireEvent.keyDown(box(), { key: 'Enter' });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenLastCalledWith(3072);
    expect(document.activeElement).not.toBe(box());
  });

  it('a later edit commits normally after an Enter', () => {
    const onChange = setup(2048);
    act(() => box().focus());
    fireEvent.change(box(), { target: { value: '3000' } });
    fireEvent.keyDown(box(), { key: 'Enter' });
    act(() => box().focus());
    fireEvent.change(box(), { target: { value: '5000' } });
    act(() => box().blur());
    expect(onChange).toHaveBeenLastCalledWith(5120);
    expect(onChange).toHaveBeenCalledTimes(2);
  });

  it('sets the --fill custom property that draws the filled track', () => {
    render(<Slider label="Top P" value={0.25} onChange={vi.fn()} min={0} max={1} step={0.01} />);
    expect(screen.getByRole('slider', { name: 'Top P' }).getAttribute('style')).toContain(
      '--fill: 25%',
    );
  });

  it('exposes the range input with its min and max', () => {
    render(<Slider label="Top P" value={0.5} onChange={vi.fn()} min={0} max={1} step={0.01} />);
    const range = screen.getByRole('slider', { name: 'Top P' });
    expect(range).toHaveAttribute('max', '1');
    expect(range).toHaveValue('0.5');
  });

  it('dragging the range reports the value', () => {
    const onChange = vi.fn();
    render(<Slider label="Top P" value={0.5} onChange={onChange} min={0} max={1} step={0.01} />);
    fireEvent.change(screen.getByRole('slider', { name: 'Top P' }), { target: { value: '0.75' } });
    expect(onChange).toHaveBeenLastCalledWith(0.75);
  });
});

describe('Field, Input and Textarea', () => {
  it('links the label, hint and error to the control', () => {
    render(
      <Field label="Name" required hint="Lowercase, no spaces" error="Name is required">
        {(control) => <Input {...control} />}
      </Field>,
    );
    const input = screen.getByLabelText(/Name/);
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-required', 'true');
    expect(input).toHaveAccessibleDescription('Name is required');
  });

  it('renders a textarea with its own control props', () => {
    render(
      <Field label="Notes">
        {(control) => <Textarea {...control} defaultValue="x" autoGrow />}
      </Field>,
    );
    expect(screen.getByLabelText('Notes').tagName).toBe('TEXTAREA');
  });
});

describe('Badge and EmptyState', () => {
  it('Badge applies its tone class', () => {
    render(<Badge tone="warning">loading</Badge>);
    expect(screen.getByText('loading')).toHaveClass('ui-badge', 'ui-badge--warning');
  });

  it('EmptyState shows title, description and action', () => {
    render(
      <EmptyState
        title="No chats yet"
        description="Start a conversation"
        action={<Button variant="primary">New chat</Button>}
      />,
    );
    expect(screen.getByText('No chats yet')).toBeInTheDocument();
    expect(screen.getByText('Start a conversation')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New chat' })).toBeInTheDocument();
  });
});

describe('Button kinds and reasons (design system)', () => {
  it('has a class per kind, including quiet and link', () => {
    render(
      <>
        <Button variant="quiet">Quiet</Button>
        <Button variant="link">Show all 24</Button>
      </>,
    );
    expect(screen.getByRole('button', { name: 'Quiet' })).toHaveClass('ui-button--quiet');
    expect(screen.getByRole('button', { name: 'Show all 24' })).toHaveClass('ui-button--link');
  });

  it('a switched-off button says why, and only while it is off', () => {
    const { rerender } = render(
      <Button disabled reason="Pick a model first">
        Send
      </Button>,
    );
    expect(screen.getByRole('button', { name: 'Send' })).toHaveAttribute(
      'aria-description',
      'Pick a model first',
    );
    rerender(<Button reason="Pick a model first">Send</Button>);
    expect(screen.getByRole('button', { name: 'Send' })).not.toHaveAttribute('aria-description');
  });
});

describe('Menu groups, ticks, keys and reasons (design system)', () => {
  it('shows a group label, the current choice, keys, and why an item is off', async () => {
    const onSelect = vi.fn();
    render(
      <Menu
        label="View"
        trigger={(props) => <Button {...props}>Open</Button>}
        items={[
          { type: 'group', id: 'g', label: 'Sort by' },
          { id: 'new', label: 'Newest', checked: true, onSelect },
          { id: 'old', label: 'Oldest', checked: false, keys: ['Ctrl', 'O'], onSelect },
          { id: 'run', label: 'Run', disabled: true, reason: 'Runner is offline', onSelect },
        ]}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Open' }));
    expect(screen.getByText('Sort by')).toHaveClass('ui-menu__group');
    expect(screen.getByRole('menuitemradio', { name: 'Newest' })).toHaveAttribute(
      'aria-checked',
      'true',
    );
    expect(screen.getByRole('menuitemradio', { name: /Oldest/ })).toHaveTextContent('CtrlO');
    expect(screen.getByRole('menuitem', { name: /Run/ })).toBeDisabled();
    expect(screen.getByText('Runner is offline')).toBeInTheDocument();
    await userEvent.keyboard('{ArrowDown}{Enter}');
    expect(onSelect).toHaveBeenCalledTimes(1);
  });
});
