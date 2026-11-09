/** The signed-in user (GET /api/me). */
import { apiJson } from './client';

export interface CurrentUser {
  id: string;
  email: string;
  role: 'admin' | 'user';
}

export const meKeys = { current: ['me'] as const };

export const meApi = {
  get: () => apiJson<CurrentUser>('/api/me'),
};
