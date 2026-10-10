import { Component, useCallback, useEffect, useMemo, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Api, errorMessage } from './api';
import { Automations } from './Automations';
import { Chat } from './Chat';
import { Activity, Reports, Settings } from './Workspace';
import type { SystemStatus } from './types';
import { Badge, Brand, ErrorNotice, Icon, useResource } from './ui';
import type { IconName } from './ui';

const API_BASE = import.meta.env.VITE_API_BASE || '';
type Session = { token: string; username: string };
type Page = 'chat' | 'automations' | 'reports' | 'activity' | 'settings';
const pages: { key: Page; name: string; icon: IconName; subtitle: string }[] = [
  { key: 'chat', name: 'Your assistant', icon: 'chat', subtitle: 'A little more room for what matters.' },
  { key: 'automations', name: 'Automations', icon: 'clock', subtitle: 'Make the everyday take care of itself.' },
  { key: 'reports', name: 'Reports', icon: 'file', subtitle: 'Research, with the sources to back it up.' },
  { key: 'activity', name: 'Activity', icon: 'activity', subtitle: 'A clear view of what your assistant is doing.' },
  { key: 'settings', name: 'Settings', icon: 'settings', subtitle: 'Your connections, preferences, and controls.' },
];

function readSession(): Session | null {
  try { const data = JSON.parse(sessionStorage.getItem('lilyleo.session') || 'null'); return data?.token && data?.username ? data : null; }
  catch { return null; }
}

function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try { onLogin(await new Api('', API_BASE).post<Session>('/v1/auth/login', { username, password })); }
    catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }
  return <main className="login-layout"><section className="login-story"><Brand/><div><span className="eyebrow light">A PERSONAL ASSISTANT. A LITTLE POSSIBILITY.</span><h1>Your day,<br/>a little lighter.</h1><p>Space to think. Help to get things done.<br/>Meet your everyday companion.</p></div><div className="orbit-art" aria-hidden="true"><div className="orbit-ring ring-one"/><div className="orbit-ring ring-two"/><div className="orbit-ring ring-three"/><span className="orbit-center"><Icon name="spark" size={60}/></span><span className="orbit-dot"/></div><span className="story-footer">LILY-LEO X <span>THOUGHTFULLY AT YOUR SIDE</span></span></section><section className="login-panel"><div className="login-box"><span className="eyebrow">YOUR PERSONAL WORKSPACE</span><h2>Welcome home.</h2><p className="muted">Sign in to pick up where you left off.</p><form onSubmit={submit}><label>Username<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required autoFocus/></label><label>Password<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required/></label><ErrorNotice message={error}/><button className="button primary full" disabled={busy}>{busy ? 'Signing in…' : 'Enter your workspace'}<Icon name="arrow" size={18}/></button></form><p className="login-note">Use the account created when your assistant service was set up.</p></div></section></main>;
}

function Workspace({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [page, setPage] = useState<Page>('chat');
  const [refresh, setRefresh] = useState(0);
  const [authError, setAuthError] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const api = useMemo(() => new Api(session.token, API_BASE, onLogout), [session.token, onLogout]);
  const changed = useCallback(() => setRefresh(value => value + 1), []);
  const status = useResource<SystemStatus>(api, '/v1/status/', refresh);
  useEffect(() => { const timer = setInterval(changed, 30_000); return () => clearInterval(timer); }, [changed]);
  async function logout() {
    setLoggingOut(true); setAuthError(null);
    try { await api.post('/v1/auth/logout'); onLogout(); }
    catch (error) { setAuthError(errorMessage(error)); }
    finally { setLoggingOut(false); }
  }
  const current = pages.find(item => item.key === page)!;
  return <div className="app-shell"><aside className="sidebar"><Brand/><div className="nav-heading">YOUR WORKSPACE</div><nav aria-label="Main navigation">{pages.map(item => <button key={item.key} className={`nav-item ${page === item.key ? 'selected' : ''}`} aria-current={page === item.key ? 'page' : undefined} onClick={() => setPage(item.key)}><Icon name={item.icon}/><span>{item.name}</span>{page === item.key && <span className="nav-dot"/>}</button>)}</nav><div className="sidebar-bottom"><div className="companion-card"><span className={`connection-dot ${status.data?.desktop_online ? 'connected' : ''}`}/><div><strong>Desktop companion</strong><small>{status.data ? (status.data.desktop_online ? 'Connected & ready' : 'Offline · jobs will wait') : 'Checking connection…'}</small></div></div><div className="profile"><span className="avatar">{session.username.slice(0, 1).toUpperCase()}</span><div><strong>{session.username}</strong><small>Personal workspace</small></div><button className="icon-button" aria-label="Sign out" title="Sign out" disabled={loggingOut} onClick={logout}><Icon name="logout" size={18}/></button></div></div></aside><main className="main-panel"><header className="topbar"><div><span className="eyebrow">LILY-LEO X / {page.toUpperCase()}</span><h1>{current.name}</h1><p>{current.subtitle}</p></div><div className="topbar-meta"><span className="date">{new Intl.DateTimeFormat('en-IN', { month: 'short', day: 'numeric', weekday: 'short', timeZone: 'Asia/Kolkata' }).format(new Date())}</span><Badge status={status.data ? (status.data.paused ? 'automations paused' : status.data.integrations.gemini ? 'ready to help' : 'setup needed') : 'connecting'}/></div></header><div className="page-content"><ErrorNotice message={authError || status.error}/>{status.data?.paused && <div className="notice warning"><Icon name="pause" size={18}/> Automations are paused. Resume them in Settings when you’re ready.</div>}{page === 'chat' && <Chat api={api} refresh={refresh} changed={changed} onAutomations={() => setPage('automations')}/>} {page === 'automations' && <Automations api={api} refresh={refresh} changed={changed}/>} {page === 'reports' && <Reports api={api} refresh={refresh}/>} {page === 'activity' && <Activity api={api} refresh={refresh} changed={changed}/>} {page === 'settings' && <Settings api={api} refresh={refresh} changed={changed} status={status.data}/>}</div><footer className="workspace-footer"><span><Icon name="spark" size={12}/> A little help, a little more possibility.</span><span>All times in Asia/Kolkata</span></footer></main></div>;
}

class ErrorBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(error: Error) { return { error: error.message }; }
  render() {
    if (this.state.error) return <main className="crash"><Brand/><h1>Let’s get back on track.</h1><p>The workspace could not display this response.</p><ErrorNotice message={this.state.error}/><button className="button primary" onClick={() => window.location.reload()}>Reload workspace</button></main>;
    return this.props.children;
  }
}

export default function App() {
  const [session, setSession] = useState<Session | null>(readSession);
  const login = useCallback((session: Session) => { sessionStorage.setItem('lilyleo.session', JSON.stringify(session)); setSession(session); }, []);
  const logout = useCallback(() => { sessionStorage.removeItem('lilyleo.session'); setSession(null); }, []);
  return <ErrorBoundary>{session ? <Workspace session={session} onLogout={logout}/> : <Login onLogin={login}/>}</ErrorBoundary>;
}
