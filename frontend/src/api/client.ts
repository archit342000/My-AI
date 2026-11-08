/** Thin fetch wrapper. Same-origin requests, JSON in and out, errors carry status and body. */

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
    throw new ApiError(response.status, parsed, message);
  }
  return response;
}

export async function apiJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await apiRequest(path, options);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
