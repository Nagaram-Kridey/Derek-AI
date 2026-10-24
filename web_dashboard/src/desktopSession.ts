import type { Api } from './api';

export function desktopLaunchCode(hash: string): string | null {
  const match = hash.match(/^#desktop-session=([A-Za-z0-9_-]{43})$/);
  return match?.[1] || null;
}

type DesktopSession = { token: string; username: string };
let exchange: Promise<DesktopSession> | null = null;
let launchCode: string | null = null;
export function exchangeDesktopLaunch(api: Api, code: string): Promise<DesktopSession> {
  // React StrictMode replays effects. Both effects share the single-use exchange.
  if (launchCode && launchCode !== code) return Promise.reject(new Error('A new desktop handoff requires a new document.'));
  launchCode = code;
  exchange ??= api.post<DesktopSession>('/v1/local/session/exchange/', { code });
  return exchange;
}
