import { act, fireEvent, render, screen } from '@testing-library/react';
import { useRef } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { filesIn, useFileDrop } from './useFileDrop';

function Harness({ onFiles }: { onFiles: (files: File[]) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const { dragging } = useFileDrop(ref, onFiles);
  return (
    <main data-testid="zone">
      <div ref={ref} />
      {dragging ? <span>drop here</span> : null}
    </main>
  );
}

const file = (name: string) => new File(['x'], name);
const withFiles = (...files: File[]) => ({ dataTransfer: { types: ['Files'], files } });

describe('useFileDrop', () => {
  it('stages the dropped files and shows the drop state only while dragging them over', () => {
    const onFiles = vi.fn();
    render(<Harness onFiles={onFiles} />);
    const zone = screen.getByTestId('zone');
    fireEvent.dragEnter(zone, withFiles(file('a.txt'), file('b.txt')));
    expect(screen.getByText('drop here')).toBeTruthy();
    fireEvent.drop(zone, withFiles(file('a.txt'), file('b.txt')));
    expect(onFiles).toHaveBeenCalledTimes(1);
    expect(onFiles.mock.calls[0]?.[0].map((f: File) => f.name)).toEqual(['a.txt', 'b.txt']);
    expect(screen.queryByText('drop here')).toBeNull();
  });

  it('a drag that carries no files (text, a link) shows no drop state and drops nothing', () => {
    const onFiles = vi.fn();
    render(<Harness onFiles={onFiles} />);
    const zone = screen.getByTestId('zone');
    fireEvent.dragEnter(zone, { dataTransfer: { types: ['text/plain'], files: [] } });
    expect(screen.queryByText('drop here')).toBeNull();
    fireEvent.drop(zone, { dataTransfer: { types: ['text/plain'], files: [] } });
    expect(onFiles).not.toHaveBeenCalled();
  });

  it('the drop state ends when the drag leaves, counting nested enters', () => {
    render(<Harness onFiles={() => undefined} />);
    const zone = screen.getByTestId('zone');
    fireEvent.dragEnter(zone, withFiles(file('a')));
    fireEvent.dragEnter(zone, withFiles(file('a')));
    fireEvent.dragLeave(zone, withFiles(file('a')));
    expect(screen.getByText('drop here')).toBeTruthy();
    fireEvent.dragLeave(zone, withFiles(file('a')));
    expect(screen.queryByText('drop here')).toBeNull();
  });

  it('a cancelled drag (dragend) or a drop elsewhere ends the drop state', () => {
    render(<Harness onFiles={() => undefined} />);
    const zone = screen.getByTestId('zone');
    fireEvent.dragEnter(zone, withFiles(file('a')));
    expect(screen.getByText('drop here')).toBeTruthy();
    fireEvent.dragEnd(window);
    expect(screen.queryByText('drop here')).toBeNull();
    fireEvent.dragEnter(zone, withFiles(file('a')));
    fireEvent.drop(window);
    expect(screen.queryByText('drop here')).toBeNull();
  });

  it('removes its listeners when unmounted', () => {
    const onFiles = vi.fn();
    const view = render(<Harness onFiles={onFiles} />);
    const zone = screen.getByTestId('zone');
    view.unmount();
    act(() => {
      zone.dispatchEvent(new Event('drop'));
    });
    expect(onFiles).not.toHaveBeenCalled();
  });
});

describe('filesIn', () => {
  it("lists a transfer's files, and nothing for no transfer", () => {
    expect(filesIn(null)).toEqual([]);
    expect(filesIn({ files: [file('a')] } as unknown as DataTransfer).map((f) => f.name)).toEqual([
      'a',
    ]);
  });
});
