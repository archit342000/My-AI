import { act, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useStreamStore } from '../state/stream-store';
import { HeaderStatus } from './HeaderStatus';
import { PageTitleSlot } from './page-header-context';
import { PageTitle } from './PageTitle';

// The pieces of the app header: the page title place and the status light.

afterEach(() => {
  vi.restoreAllMocks();
  act(() => useStreamStore.getState().finish());
});

describe('PageTitle', () => {
  it('renders into the header slot when there is one', () => {
    function Frame() {
      const [slot, setSlot] = useState<HTMLElement | null>(null);
      return (
        <>
          <header ref={setSlot} data-testid="slot" />
          <PageTitleSlot.Provider value={slot}>
            <section data-testid="page">
              <PageTitle>Logs</PageTitle>
            </section>
          </PageTitleSlot.Provider>
        </>
      );
    }
    render(<Frame />);
    expect(screen.getByTestId('slot')).toHaveTextContent('Logs');
    expect(screen.getByTestId('page')).toBeEmptyDOMElement();
  });

  it('renders in place when the page is shown without the app header', () => {
    render(<PageTitle>Logs</PageTitle>);
    expect(screen.getByText('Logs')).toHaveClass('main-title');
  });
});

describe('HeaderStatus', () => {
  it('says Ready, then Thinking while a reply is written, then Stopping', () => {
    render(<HeaderStatus onSphere={false} />);
    expect(screen.getByRole('status')).toHaveTextContent('Ready');
    act(() => useStreamStore.getState().start('c1', null, new AbortController()));
    expect(screen.getByRole('status')).toHaveTextContent('Thinking');
    act(() => useStreamStore.getState().setStopping(true));
    expect(screen.getByRole('status')).toHaveTextContent('Stopping');
  });

  it('says Offline when the browser has no connection', () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    render(<HeaderStatus onSphere={false} />);
    expect(screen.getByRole('status')).toHaveTextContent('Offline');
  });

  it('on an open screen it sits on the sphere with the fade behind it', () => {
    const { container } = render(<HeaderStatus onSphere />);
    expect(container.querySelector('.on-sphere .fade-layer')).not.toBeNull();
  });
});
