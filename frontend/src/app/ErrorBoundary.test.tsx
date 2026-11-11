import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router';
import { GonePage, NotFoundPage } from './DeadEnds';
import { ErrorBoundary } from './ErrorBoundary';

let broken = true;
function Flaky() {
  if (broken) throw new TypeError('x is undefined');
  return <p>the screen</p>;
}

describe('ErrorBoundary', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    broken = true;
  });

  it('shows "Something broke on our side" instead of a blank page, with the error behind Show details', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    render(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Something broke on our side.');
    expect(
      screen.getByText('Nothing you did. Your work up to the last save is safe.'),
    ).toBeTruthy();
    expect(screen.queryByText(/x is undefined/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Show details' }));
    expect(screen.getByText('TypeError: x is undefined')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Go to Home' })).toBeTruthy();
  });

  it('Try again draws the screen once more', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    render(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>,
    );
    broken = false;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(screen.getByText('the screen')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('shows the screen untouched when nothing fails', () => {
    broken = false;
    render(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>,
    );
    expect(screen.getByText('the screen')).toBeTruthy();
  });
});

describe('dead-end pages', () => {
  const at = (ui: React.ReactNode) =>
    render(
      <MemoryRouter initialEntries={['/nowhere']}>
        <Routes>
          <Route path="/" element={<p>home</p>} />
          <Route path="*" element={ui} />
        </Routes>
      </MemoryRouter>,
    );

  it('an address that leads nowhere says so and leads home', () => {
    at(<NotFoundPage />);
    expect(screen.getByRole('alert')).toHaveTextContent('This page does not exist.');
    fireEvent.click(screen.getByRole('link', { name: 'Go to Home' }));
    expect(screen.getByText('home')).toBeTruthy();
  });

  it.each(['chat', 'workspace'] as const)('a %s that is gone says so', (what) => {
    at(<GonePage what={what} />);
    expect(screen.getByRole('alert')).toHaveTextContent(`This ${what} no longer exists.`);
    expect(screen.getByRole('link', { name: 'Go to Home' }).getAttribute('href')).toBe('/');
  });
});
