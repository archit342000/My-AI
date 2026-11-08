import { useState } from 'react';
import { ContextMenu, type MenuItem } from '../../components/ui/ContextMenu';
import { Modal } from '../../components/ui/Modal';
import { showToast } from '../../components/ui/toast-store';

/** Dev-only page (route /dev/ui) for checking primitives in the browser. */
export function PrimitivesDemo() {
  const [modalOpen, setModalOpen] = useState(false);
  const [nestedOpen, setNestedOpen] = useState(false);
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);

  const items: MenuItem[] = [
    { id: 'rename', label: 'Rename', icon: 'edit', onSelect: () => showToast('Renamed', 'success') },
    { id: 'delete', label: 'Delete', icon: 'trash', danger: true, onSelect: () => showToast('Deleted', 'error') },
  ];

  return (
    <div style={{ padding: '2rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
      <button type="button" className="btn-primary" onClick={() => setModalOpen(true)}>Open modal</button>
      <button type="button" className="btn-secondary" onClick={() => showToast('Saved successfully', 'success')}>Toast</button>
      <button
        type="button"
        className="btn-secondary"
        onContextMenu={(e) => {
          e.preventDefault();
          setMenu({ x: e.clientX, y: e.clientY });
        }}
      >
        Right-click for menu
      </button>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Demo modal">
        <p>Press Escape or click outside to close.</p>
        <button type="button" className="btn-secondary" onClick={() => setNestedOpen(true)}>Open nested</button>
      </Modal>
      <Modal open={nestedOpen} onClose={() => setNestedOpen(false)} title="Nested modal">
        <p>Escape closes only this dialog.</p>
      </Modal>

      {menu ? <ContextMenu x={menu.x} y={menu.y} items={items} onClose={() => setMenu(null)} /> : null}
    </div>
  );
}
