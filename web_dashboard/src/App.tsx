import { Component, useCallback, useEffect, useMemo, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Api, errorMessage } from './api';
import { Automations } from './Automations';
import { Chat } from './Chat';
import { Roadmap } from './Roadmap';
import { Features } from './Features';
import { Settings } from './Workspace';
import { Activity } from './Activity';
import { Home } from './Home';
import { Commands } from './Commands';
import { ReportLibrary } from './Reports';
import { desktopLaunchCode, exchangeDesktopLaunch } from './desktopSession';
import type { SystemStatus } from './types';
import { Badge, Brand, ErrorNotice, Icon, useResource } from './ui';
import type { IconName } from './ui';

const API_BASE = import.meta.env.VITE_API_BASE || '';
const candidateDesktopCode = desktopLaunchCode(window.location.hash);
const desktopCode = window.location.origin === 'http://127.0.0.1:8000' && !API_BASE ? candidateDesktopCode : null;
if (candidateDesktopCode) window.history.replaceState(null, '', window.location.pathname + window.location.search + '#chat');
type Session = { token: string; username: string; remember?: boolean };
type Page = 'roadmap' | 'home' | 'chat' | 'automations' | 'reports' | 'activity' | 'settings' | 'features' | 'commands';
const pages: { key: Page; name: string; icon: IconName; subtitle: string }[] = [
  {
    key: 'home',
    name: 'Today',
    icon: 'spark',
    subtitle: 'Your schedule, saved work and what needs attention.',
  },
  { key: 'chat', name: 'Chat', icon: 'chat', subtitle: 'Think, research and get things done in one conversation.' },
  {
    key: 'features',
    name: 'Features',
    icon: 'spark',
    subtitle: 'What Derek can do, and what still needs connecting.',
  },
  {
    key: 'automations',
    name: 'Tasks',
    icon: 'clock',
    subtitle: 'Scheduled reminders, research and approved workflows.',
  },
  { key: 'reports', name: 'Reports', icon: 'file', subtitle: 'Saved research, sources and verification notes.' },
  {
    key: 'activity',
    name: 'Activity',
    icon: 'activity',
    subtitle: 'A clear view of what your assistant is doing.',
  },
  {
    key: 'commands',
    name: 'Command history',
    icon: 'chat',
    subtitle: 'Every request, its saved result, and what needs your review.',
  },
  {
    key: 'settings',
    name: 'Settings',
    icon: 'settings',
    subtitle: 'Your connections, preferences, and controls.',
  },
  { key: 'roadmap', name: 'Roadmap', icon: 'spark', subtitle: 'Priorities, acceptance evidence and ideas for later.' },
];
const primaryPages: Page[] = ['chat', 'automations', 'reports', 'home'];

function readSession(): Session | null {
  try {
    const data = JSON.parse(
      sessionStorage.getItem('lilyleo.session') || localStorage.getItem('derek.remembered-session') || 'null',
    );
    return typeof data?.token === 'string' &&
      /^[a-f0-9]{40}$/i.test(data.token) &&
      typeof data?.username === 'string' &&
      data.username.length > 0
      ? data
      : null;
  } catch {
    return null;
  }
}

function Login({ onLogin, notice }: { onLogin: (session: Session) => void; notice?: string }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(notice || null);
  const [busy, setBusy] = useState(false);
  const [remember, setRemember] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onLogin({
        ...(await new Api('', API_BASE).post<Session>('/v1/auth/login', { username, password })),
        remember,
      });
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-layout">
      <section className="login-story">
        <Brand />
        <div>
          <span className="eyebrow light">A PERSONAL ASSISTANT. A LITTLE POSSIBILITY.</span>
          <h1>
            Your day,
            <br />a little lighter.
          </h1>
          <p>
            Space to think. Help to get things done.
            <br />
            Meet your everyday companion.
          </p>
        </div>
        <div className="orbit-art" aria-hidden="true">
          <div className="orbit-ring ring-one" />
          <div className="orbit-ring ring-two" />
          <div className="orbit-ring ring-three" />
          <span className="orbit-center">
            <Icon name="spark" size={60} />
          </span>
          <span className="orbit-dot" />
        </div>
        <span className="story-footer">
          DEREK <span>THOUGHTFULLY AT YOUR SIDE</span>
        </span>
      </section>
      <section className="login-panel">
        <div className="login-box">
          <span className="eyebrow">YOUR PERSONAL WORKSPACE</span>
          <h2>Welcome home.</h2>
          <p className="muted">Sign in to pick up where you left off.</p>
          <form onSubmit={submit}>
            <label>
              Username
              <input
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            <label className="checkbox-label remember-option">
              <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
              Keep me signed in on this browser
            </label>
            <ErrorNotice message={error} />
            <button className="button primary full" disabled={busy}>
              {busy ? 'Signing in…' : 'Enter your workspace'}
              <Icon name="arrow" size={18} />
            </button>
          </form>
          <p className="login-note">Use the account created when your assistant service was set up.</p>
        </div>
      </section>
    </main>
  );
}

function Workspace({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const currentPage = () =>
    pages.find((item) => item.key === window.location.hash.slice(1).split('?')[0])?.key || 'chat';
  const [page, updatePage] = useState<Page>(currentPage);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [todayOpen, setTodayOpen] = useState(false);
  const [settingsFocus, setSettingsFocus] = useState('');
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    try { return localStorage.getItem('derek.theme') === 'light' ? 'light' : 'dark'; } catch { return 'dark'; }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('derek.theme', theme); } catch { /* Optional preference storage. */ }
  }, [theme]);
  useEffect(() => {
    const dismiss = (event: KeyboardEvent) => { if (event.key === 'Escape') setProfileOpen(false); };
    window.addEventListener('keydown', dismiss);
    return () => window.removeEventListener('keydown', dismiss);
  }, []);
  const setPage = (value: Page) => {
    window.location.hash = value;
    updatePage(value);
    setProfileOpen(false);
  };
  useEffect(() => {
    const update = () => updatePage(currentPage());
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  const [refresh, setRefresh] = useState(0);
  const [authError, setAuthError] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const api = useMemo(() => new Api(session.token, API_BASE, onLogout), [session.token, onLogout]);
  const changed = useCallback(() => setRefresh((value) => value + 1), []);
  const status = useResource<SystemStatus>(api, '/v1/status/', refresh);
  useEffect(() => {
    const timer = setInterval(() => {
      if (!document.hidden) changed();
    }, 10_000);
    const foreground = () => {
      if (!document.hidden) changed();
    };
    document.addEventListener('visibilitychange', foreground);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', foreground);
    };
  }, [changed]);
  async function logout() {
    setLoggingOut(true);
    setAuthError(null);
    try {
      await api.post('/v1/auth/logout');
      onLogout();
    } catch (error) {
      setAuthError(errorMessage(error));
    } finally {
      setLoggingOut(false);
    }
  }
  useEffect(() => {
    if (page !== 'settings' || !settingsFocus) return;
    const frame = requestAnimationFrame(() => {
      const heading = Array.from(document.querySelectorAll('h2,h3')).find(item => item.textContent === settingsFocus);
      if (heading instanceof HTMLElement) { heading.tabIndex = -1; heading.focus(); heading.scrollIntoView({ block: 'start', behavior: 'instant' }); }
    });
    return () => cancelAnimationFrame(frame);
  }, [page, settingsFocus]);
  const openSettings = (heading: string) => { setSettingsFocus(heading); setPage('settings'); };
  const current = pages.find((item) => item.key === page)!;
  return (
    <div className={`app-shell derek-workspace ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      <a className="skip-link" href="#main-content" onClick={(event) => { event.preventDefault(); document.getElementById('main-content')?.focus(); }}>Skip to content</a>
      <aside className="sidebar">
        <div className="sidebar-brand"><Brand /><button className="icon-button sidebar-toggle" onClick={() => setSidebarCollapsed(!sidebarCollapsed)} aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!sidebarCollapsed}><Icon name="chevron" /></button></div>
        <nav aria-label="Main navigation">{primaryPages.map(key => pages.find(item => item.key === key)!).map(item => <button key={item.key} className={`nav-item ${page === item.key ? 'selected' : ''}`} aria-label={item.name} title={sidebarCollapsed ? item.name : undefined} aria-current={page === item.key ? 'page' : undefined} onClick={() => setPage(item.key)}><Icon name={item.icon} /><span>{item.name}</span></button>)}</nav>
        <div className="sidebar-bottom"><small>{status.data?.desktop_online ? 'Companion connected' : 'Companion offline'}</small><p>{session.username}</p></div>
      </aside>
      <div className="profile-control">
        <button className="button profile-trigger" aria-expanded={profileOpen} aria-controls="profile-options" onClick={() => setProfileOpen(!profileOpen)}><span className="avatar">{session.username.slice(0, 1).toUpperCase()}</span><span>Profile</span></button>
        {profileOpen && <div id="profile-options" className="profile-options" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setProfileOpen(false); }}>
          <strong>{session.username}</strong>
          <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>Appearance · {theme === 'dark' ? 'Switch to light' : 'Switch to dark'}</button>
          <button onClick={() => openSettings('Connections')}>Connections & models</button>
          <button onClick={() => openSettings('Desktop voice access')}>Voice</button>
          <button onClick={() => openSettings('Your data')}>Privacy & memory</button>
          <button onClick={() => setPage('commands')}>Request history</button>
          <button onClick={() => setPage('activity')}>Activity & notifications</button>
          <button onClick={() => setPage('features')}>Capabilities</button>
          <button onClick={() => setPage('roadmap')}>Build & roadmap</button>
          <button disabled={loggingOut} onClick={logout}>Sign out</button>
        </div>}
      </div>
      <main className="main-panel" id="main-content" tabIndex={-1}>
        <header className="topbar">
          <div>

            <h1>{current.name}</h1>
            <p>{current.subtitle}</p>
          </div>
          <div className="topbar-meta">
            <span className="date">
              {new Intl.DateTimeFormat('en-IN', {
                month: 'short',
                day: 'numeric',
                weekday: 'short',
                timeZone: 'Asia/Kolkata',
              }).format(new Date())}
            </span>
            <Badge
              status={
                status.error
                  ? 'service unreachable'
                  : status.data
                    ? status.data.paused
                      ? 'automations paused'
                      : status.data.runtime?.managed
                        ? 'local service connected'
                        : 'service connected'
                    : 'connecting'
              }
            />
          </div>
        </header>
        <div className="page-content">
          <ErrorNotice message={authError || status.error} />
          {status.data?.paused && (
            <div className="notice warning">
              <Icon name="pause" size={18} /> Automations are paused. Resume them in Settings when you’re
              ready.
            </div>
          )}
          {page === 'home' && (
            <Home
              api={api}
              refresh={refresh}
              changed={changed}
              status={status.data}
              username={session.username}
              navigate={setPage}
            />
          )}{' '}
          {page === 'commands' && <Commands api={api} refresh={refresh} changed={changed} />}{' '}
          {page === 'chat' && (
            <div className={`conversation-layout ${todayOpen ? 'today-expanded' : ''}`}><div className="conversation-main"><button className="button today-toggle" aria-expanded={todayOpen} aria-controls="chat-today" onClick={() => setTodayOpen(!todayOpen)}>{todayOpen ? 'Hide Today' : 'Show Today'}</button><Chat
              api={api}
              refresh={refresh}
              changed={changed}
              onAutomations={() => setPage('automations')}
              localVoice={status.data?.runtime?.managed}
            /></div>{todayOpen && <aside id="chat-today" className="chat-today" aria-label="Today"><Home api={api} refresh={refresh} changed={changed} status={status.data} username={session.username} navigate={setPage} /></aside>}</div>
          )}{' '}
          {page === 'automations' && <Automations api={api} refresh={refresh} changed={changed} />}{' '}
          {page === 'reports' && <ReportLibrary api={api} refresh={refresh} changed={changed} />}{' '}
          {page === 'activity' && <Activity api={api} refresh={refresh} changed={changed} />}{' '}
          <div hidden={page !== 'roadmap'}><Roadmap api={api} /></div>
          {page === 'features' && <Features api={api} refresh={refresh} changed={changed} />}{' '}
          {page === 'settings' && (
            <Settings api={api} refresh={refresh} changed={changed} status={status.data} />
          )}
        </div>
        <footer className="workspace-footer">
          <span>
            <Icon name="monitor" size={12} /> Derek · Your personal workspace
          </span>
          <span>All times in Asia/Kolkata</span>
        </footer>
      </main>
      <nav className="bottom-navigation" aria-label="Main navigation">{primaryPages.map(key => pages.find(item => item.key === key)!).map(item => <button key={item.key} aria-current={page === item.key ? 'page' : undefined} onClick={() => setPage(item.key)}><Icon name={item.icon} /><span>{item.name}</span></button>)}</nav>
    </div>
  );
}

class ErrorBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(error: Error) {
    return { error: error.message };
  }
  render() {
    if (this.state.error)
      return (
        <main className="crash">
          <Brand />
          <h1>Let’s get back on track.</h1>
          <p>The workspace could not display this response.</p>
          <ErrorNotice message={this.state.error} />
          <button className="button primary" onClick={() => window.location.reload()}>
            Reload workspace
          </button>
        </main>
      );
    return this.props.children;
  }
}

export default function App() {
  const [session, setSession] = useState<Session | null>(() => desktopCode ? null : readSession());
  const [connecting, setConnecting] = useState(Boolean(desktopCode));
  const [desktopError, setDesktopError] = useState('');
  const login = useCallback((session: Session) => {
    try {
      sessionStorage.setItem('lilyleo.session', JSON.stringify(session));
    } catch {
      /* In-memory sign-in still works when browser storage is disabled. */
    }
    try {
      if (session.remember) localStorage.setItem('derek.remembered-session', JSON.stringify(session));
      else localStorage.removeItem('derek.remembered-session');
    } catch {
      /* Remembering this browser is optional. */
    }
    setSession(session);
  }, []);
  const logout = useCallback(() => {
    try {
      sessionStorage.removeItem('lilyleo.session');
    } catch {
      /* Storage may be disabled. */
    }
    try {
      localStorage.removeItem('derek.remembered-session');
    } catch {
      /* Storage may be disabled. */
    }
    setSession(null);
  }, []);
  useEffect(() => {
    if (!desktopCode) return;
    let active = true;
    exchangeDesktopLaunch(new Api(''), desktopCode)
      .then(value => { if (active) login(value); })
      .catch(() => { if (active) setDesktopError('Desktop sign-in expired or was revoked. Close this Derek window and reopen from the tray, or sign in below.'); })
      .finally(() => { if (active) setConnecting(false); });
    return () => { active = false; };
  }, [login]);
  return (
    <ErrorBoundary>
      {connecting ? <main className="crash"><Brand /><p>Connecting your desktop session…</p></main> : session ? <Workspace session={session} onLogout={logout} /> : <Login onLogin={login} notice={desktopError} />}
    </ErrorBoundary>
  );
}
