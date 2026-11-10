import { useState } from 'react';
import { Badge } from '../../components/ui/Badge';
import { Checkbox } from '../../components/ui/Checkbox';
import { Chip } from '../../components/ui/Chip';
import { Kbd } from '../../components/ui/Kbd';
import { StatusLight } from '../../components/ui/StatusLight';
import { Tabs } from '../../components/ui/Tabs';
import { Tag } from '../../components/ui/Tag';
import { TickRule } from '../../components/ui/TickRule';
import { Button, IconButton } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { Field, Input, Textarea } from '../../components/ui/Field';
import { Menu, type MenuEntry } from '../../components/ui/Menu';
import { Modal } from '../../components/ui/Modal';
import { RadioCards } from '../../components/ui/RadioCards';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { Select, type SelectOption } from '../../components/ui/Select';
import { Slider } from '../../components/ui/Slider';
import { Toggle } from '../../components/ui/Toggle';
import { Tooltip } from '../../components/ui/Tooltip';
import { showToast } from '../../components/ui/toast-store';
import { FoundationsDemo } from './FoundationsDemo';

const MODELS: SelectOption[] = [
  { value: 'qwen', label: 'Qwen 3.5 4B', group: 'Local', dot: 'success' },
  { value: 'nemotron', label: 'Nemotron 30B', group: 'Local', dot: 'warning' },
  { value: 'gpt', label: 'Hosted model', group: 'Other', hint: 'remote' },
];

/** Dev-only page (route /dev/ui) for checking primitives in the browser. */
export function PrimitivesDemo() {
  const [modalOpen, setModalOpen] = useState(false);
  const [nestedOpen, setNestedOpen] = useState(false);
  const [model, setModel] = useState('qwen');
  const [view, setView] = useState('preview');
  const [style, setStyle] = useState('precise');
  const [vision, setVision] = useState(false);
  const [temperature, setTemperature] = useState(0.7);
  const [ticked, setTicked] = useState<boolean | 'mixed'>('mixed');
  const [tab, setTab] = useState('network');

  const menuItems: MenuEntry[] = [
    {
      id: 'rename',
      label: 'Rename',
      icon: 'edit',
      onSelect: () => showToast('Renamed', 'success'),
    },
    { type: 'separator', id: 'sep' },
    {
      type: 'submenu',
      id: 'move',
      label: 'Move to workspace',
      searchable: true,
      items: ['Work', 'Research', 'Home'].map((name) => ({
        id: name,
        label: name,
        onSelect: () => showToast(`Moved to ${name}`, 'success'),
      })),
    },
    { type: 'separator', id: 'sep2' },
    {
      id: 'delete',
      label: 'Delete',
      icon: 'trash',
      danger: true,
      onSelect: () => showToast('Deleted', 'error'),
    },
  ];

  return (
    <div className="ui-demo">
      <FoundationsDemo />

      <section className="ui-demo__section">
        <h2>Buttons and icon buttons</h2>
        <div className="ui-demo__row">
          <Button variant="primary">Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button variant="secondary" loading>
            Saving
          </Button>
          <Button variant="secondary" size="sm">
            Small
          </Button>
          <IconButton icon="edit" label="Edit" />
          <IconButton icon="trash" label="Delete" tone="danger" />
          <IconButton icon="close" label="Close" size="sm" />
          <Button onClick={() => setModalOpen(true)}>Open modal</Button>
          <Button onClick={() => showToast('Saved successfully', 'success')}>Toast</Button>
        </div>
        <div className="ui-demo__row">
          <Tooltip content="Tooltip text">
            <Button variant="ghost">Hover me</Button>
          </Tooltip>
          <Menu
            items={menuItems}
            label="Chat actions"
            trigger={(props) => <Button {...props}>Menu</Button>}
          />
        </div>
      </section>

      <section className="ui-demo__section">
        <h2>Button kinds, labels and small pieces</h2>
        <div className="ui-demo__row">
          <Button variant="primary">Solid</Button>
          <Button variant="quiet">Quiet</Button>
          <Button variant="secondary">Outline</Button>
          <Button variant="ghost">Plain</Button>
          <Button variant="danger">Danger</Button>
          <Button variant="link">Show all 24</Button>
          <Button aria-pressed="true">On</Button>
          <Button disabled reason="Pick a model first">
            Off, with a reason
          </Button>
        </div>
        <div className="ui-demo__row">
          <StatusLight label="Ready" />
          <StatusLight label="Thinking" busy />
          <StatusLight label="Saved" tone="ok" />
          <StatusLight label="Offline" tone="warn" />
          <StatusLight label="Failed" tone="bad" />
          <Chip>notes.md</Chip>
          <Chip tint removeLabel="Switch off Web search" onRemove={() => showToast('Off', 'info')}>
            Web search
          </Chip>
          <Tag>Python</Tag>
          <Badge tone="accent">v3</Badge>
          <span className="ui-count">3</span>
          <span className="ui-count ui-count--quiet">12</span>
          <Kbd keys={['Ctrl', 'K']} />
        </div>
        <TickRule />
        <div className="ui-demo__row">
          <Checkbox checked={ticked} onChange={setTicked}>
            Tick box (starts mixed)
          </Checkbox>
          <Tabs
            label="Log kind"
            value={tab}
            onChange={setTab}
            options={[
              { value: 'network', label: 'Network' },
              { value: 'events', label: 'Events' },
              { value: 'app', label: 'App' },
              { value: 'database', label: 'Database' },
            ]}
          />
        </div>
      </section>

      <section className="ui-demo__section">
        <h2>Select, segmented, radio cards</h2>
        <div className="ui-demo__stack">
          <Select
            aria-label="Model"
            value={model}
            onChange={setModel}
            options={MODELS}
            searchable
          />
          <SegmentedControl
            label="View"
            value={view}
            onChange={setView}
            options={[
              { value: 'preview', label: 'Preview', icon: 'file-text' },
              { value: 'edit', label: 'Edit', icon: 'edit' },
            ]}
          />
          <RadioCards
            label="Style"
            value={style}
            onChange={setStyle}
            options={[
              { value: 'precise', title: 'Precise', description: 'Short, factual answers' },
              { value: 'creative', title: 'Creative', description: 'More varied wording' },
            ]}
          />
        </div>
      </section>

      <section className="ui-demo__section">
        <h2>Toggle, slider, fields</h2>
        <div className="ui-demo__stack">
          <Toggle
            checked={vision}
            onChange={setVision}
            label="Vision"
            description="Send images to the model"
          />
          <Slider
            label="Temperature"
            value={temperature}
            onChange={setTemperature}
            min={0}
            max={2}
            step={0.05}
          />
          <Field label="Skill name" required hint="Lowercase letters and dashes">
            {(control) => <Input {...control} placeholder="my-skill" mono />}
          </Field>
          <Field label="Instructions" error="Add at least one instruction">
            {(control) => <Textarea {...control} placeholder="Write the instructions" autoGrow />}
          </Field>
        </div>
      </section>

      <section className="ui-demo__section">
        <h2>Badges and empty state</h2>
        <div className="ui-demo__row">
          <Badge>Default</Badge>
          <Badge tone="success">Loaded</Badge>
          <Badge tone="warning">Loading</Badge>
          <Badge tone="danger">Error</Badge>
          <Badge tone="accent">New</Badge>
        </div>
        <EmptyState
          icon="folder"
          title="No workspaces yet"
          description="Group related chats and files in a workspace."
          action={<Button variant="primary">New workspace</Button>}
        />
      </section>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Demo modal">
        <p>Press Escape or click outside to close.</p>
        <Button onClick={() => setNestedOpen(true)}>Open nested</Button>
      </Modal>
      <Modal open={nestedOpen} onClose={() => setNestedOpen(false)} title="Nested modal">
        <p>Escape closes only this dialog.</p>
      </Modal>
    </div>
  );
}
