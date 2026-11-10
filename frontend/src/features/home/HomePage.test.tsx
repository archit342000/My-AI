import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { HomePage } from './HomePage';

describe('HomePage', () => {
  it('shows the welcome hero (the composer lives in the layout)', () => {
    renderWithProviders(<HomePage />);
    expect(screen.getByText('Hello there')).toBeTruthy();
    expect(screen.getByText('How can I help you today?')).toBeTruthy();
    expect(screen.queryByPlaceholderText('Type a message…')).toBeNull();
  });
});
