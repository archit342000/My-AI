/** Thin fetch wrapper. Same-origin requests, JSON in and out, errors carry status and body. */
import { showToast } from '../components/ui/toast-store';
import { useUserStore } from '../state/user-store';

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

/** Query retry rule: one retry, except for 401 and 403, which a retry cannot change (and would toast twice). */
export function shouldRetryQuery(count: number, err: unknown): boolean {
  return !(err instanceof ApiError && (err.status === 401 || err.status === 403)) && count < 1;
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  json?: unknown;
  body?: BodyInit | null;
}

export async function apiRequest(path: string, options: RequestOptions = {}): Promise<Response> {
  const { json, headers, body, ...rest } = options;
  const finalHeaders = new Headers(headers);
  let finalBody: BodyInit | null | undefined = body;
  if (json !== undefined) {
    finalHeaders.set('Content-Type', 'application/json');
    finalBody = JSON.stringify(json);
  }
  const response = await fetch(path, {
    credentials: 'same-origin',
    ...rest,
    headers: finalHeaders,
    body: finalBody,
  });
  if (!response.ok) {
    const text = await response.text();
    let parsed: unknown = text;
    try {
      parsed = JSON.parse(text);
    } catch {
      /* body is not JSON; keep the raw text */
    }
    const message =
      (parsed && typeof parsed === 'object' && 'error' in parsed && typeof parsed.error === 'string'
        ? parsed.error
        : null) ?? `${response.status} ${response.statusText || 'request failed'}`;
    // 401: the Access session ended (RootLayout shows a reload banner). 403: the server refused the action
    // for this user; tell them once per response and still throw so callers keep their own flow.
    if (response.status === 401) useUserStore.getState().setSessionExpired(true);
    else if (response.status === 403) showToast("You don't have access to that.", 'error');
    throw new ApiError(response.status, parsed, message);
  }
  return response;
}

export async function apiJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await apiRequest(path, options);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
