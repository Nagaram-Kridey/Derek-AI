export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.';
}

export function safeHttpUrl(value?: string): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}

function readableError(data: unknown): string {
  if (typeof data === 'string') return data;
  if (data && typeof data === 'object') {
    const item = data as Record<string, unknown>;
    if (typeof item.detail === 'string') return item.detail;
    if (typeof item.error === 'string') return item.error;
    return Object.entries(item)
      .map(([field, value]) => `${field}: ${Array.isArray(value) ? value.join(', ') : JSON.stringify(value)}`)
      .join(' · ');
  }
  return 'Request could not be completed.';
}

export class Api {
  token: string;
  base: string;
  onUnauthorized?: () => void;
  constructor(token: string, base = '', onUnauthorized?: () => void) {
    this.token = token;
    this.base = base.replace(/\/$/, '');
    this.onUnauthorized = onUnauthorized;
  }

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await this.fetch(path, options);
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  async fetch(path: string, options: RequestInit = {}): Promise<Response> {
    // Keep credentials confined to this API, even when report content contains URLs.
    if (
      !path.startsWith('/v1/') ||
      path.includes('\\') ||
      !new URL(path, 'http://derek.local').pathname.startsWith('/v1/')
    )
      throw new Error('Invalid API path.');
    const headers = new Headers(options.headers);
    if (this.token) headers.set('Authorization', `Token ${this.token}`);
    if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
    let response: Response;
    try {
      response = await fetch(`${this.base}${path}`, {
        ...options,
        headers,
        credentials: 'same-origin',
        redirect: 'error',
      });
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') throw error;
      throw new Error('Cannot reach the assistant service. Check your connection and try again.');
    }
    if (!response.ok) {
      let detail: unknown;
      try {
        detail = await response.json();
      } catch {
        detail = `Request failed (${response.status}).`;
      }
      if (response.status === 401 && this.token) this.onUnauthorized?.();
      throw new ApiError(readableError(detail), response.status);
    }
    return response;
  }

  post<T>(path: string, data: unknown = {}): Promise<T> {
    return this.request<T>(path, { method: 'POST', body: JSON.stringify(data) });
  }

  delete(path: string): Promise<void> {
    return this.request<void>(path, { method: 'DELETE' });
  }

  async download(path: string, filename: string): Promise<void> {
    const response = await this.fetch(path);
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename.replace(/[<>:"/\\|?*\x00-\x1F]/g, '_');
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
