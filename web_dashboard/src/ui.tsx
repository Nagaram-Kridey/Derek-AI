import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Api, errorMessage } from './api';

export type IconName = 'spark' | 'chat' | 'clock' | 'file' | 'activity' | 'settings' | 'arrow' | 'plus' | 'close' | 'mic' | 'download' | 'check' | 'logout' | 'monitor' | 'pause' | 'play' | 'refresh' | 'link' | 'chevron';
const paths: Record<IconName, ReactNode> = {
  spark: <><path d="m12 3 2.8 6.2L21 12l-6.2 2.8L12 21l-2.8-6.2L3 12l6.2-2.8Z"/><path d="m20 2 .6 1.4L22 4l-1.4.6L20 6l-.6-1.4L18 4l1.4-.6Z"/></>,
  chat: <path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z"/>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h5"/></>,
  activity: <path d="M3 12h4l3-8 4 16 3-8h4"/>,
  settings: <><path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="10" cy="18" r="2"/></>,
  arrow: <path d="M5 12h14m-5-5 5 5-5 5"/>,
  plus: <path d="M12 5v14M5 12h14"/>,
  close: <path d="m6 6 12 12M6 18 18 6"/>,
  mic: <><rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8"/></>,
  download: <><path d="M12 3v12m-5-5 5 5 5-5M5 17v4h14v-4"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  logout: <><path d="M9 4H4v16h5M13 12h8m-4-4 4 4-4 4"/></>,
  monitor: <><rect x="3" y="3" width="18" height="13" rx="2"/><path d="M12 16v5m-4 0h8"/></>,
  pause: <><path d="M8 5v14M16 5v14"/></>,
  play: <path d="m8 4 12 8-12 8Z"/>,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-2l2 2M4 17l2 2a7 7 0 0 0 12-2"/></>,
  link: <><path d="m10 13 4-4M8 15l-2 2a4 4 0 0 0 6 6l4-4a4 4 0 0 0 0-6M16 9l2-2a4 4 0 0 0-6-6L8 5a4 4 0 0 0 0 6" transform="translate(0 1) scale(.9)"/></>,
  chevron: <path d="m9 5 7 7-7 7"/>,
};
export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
export function Brand() { return <div className="brand"><span className="brand-mark"><Icon name="spark" size={24}/></span><span>Lily-Leo <small>X</small></span></div>; }
export function ErrorNotice({ message }: { message: string | null }) { return message ? <div className="notice error" role="alert">{message}</div> : null; }
export function Empty({ icon = 'spark', title, children }: { icon?: IconName; title: string; children: ReactNode }) { return <div className="empty"><span className="empty-icon"><Icon name={icon} size={28}/></span><h3>{title}</h3><p>{children}</p></div>; }
export function Badge({ status = 'draft' }: { status?: string | boolean }) {
  const value = typeof status === 'boolean' ? (status ? 'enabled' : 'paused') : status;
  const tone = /success|complete|enabled|active|connected|online|approved/.test(value) ? 'good' : /fail|error|rejected|cancel/.test(value) ? 'bad' : /pending|approval|paused|waiting|offline/.test(value) ? 'warm' : '';
  return <span className={`badge ${tone}`}>{value.replaceAll('_', ' ')}</span>;
}
export function dateLabel(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' }).format(date);
}
export function JsonDetails({ value, label = 'View details' }: { value: unknown; label?: string }) {
  return value == null ? null : <details className="json-details"><summary>{label}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>;
}
export function useResource<T>(api: Api, path: string, refresh = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    api.request<T>(path, { signal: controller.signal }).then(value => { setData(value); setError(null); }).catch(error => { if (!controller.signal.aborted) setError(errorMessage(error)); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [api, path, refresh]);
  return { data, error, loading, setData };
}
export function Loading() { return <div className="loading" role="status"><span className="loader"/> Loading your workspace…</div>; }
export function Modal({ title, children, close }: { title: string; children: ReactNode; close: () => void }) {
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLDialogElement>('#workspace-dialog');
    dialog?.showModal();
    return () => { dialog?.close(); previous?.focus(); };
  }, []);
  return <dialog id="workspace-dialog" className="modal" aria-labelledby="dialog-title" onCancel={event => { event.preventDefault(); close(); }}><div className="modal-heading"><h2 id="dialog-title">{title}</h2><button className="icon-button" onClick={close} aria-label="Close dialog"><Icon name="close"/></button></div>{children}</dialog>;
}
