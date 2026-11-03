import { Component, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Api, errorMessage } from './api';
import { Login } from './Login';
import type { Session } from './Login';
import { Images } from './Images';
import { Analytics } from './Analytics';
import { Automations } from './Automations';
import { Chat } from './Chat';
import { Roadmap } from './Roadmap';
import { Features } from './Features';
import { Settings } from './Workspace';
import { TrialSettings } from './TrialSettings';
import { Activity } from './Activity';
import { Home } from './Home';
import { Commands } from './Commands';
import { ReportLibrary } from './Reports';
import { desktopLaunchCode, exchangeDesktopLaunch } from './desktopSession';
import type { SystemStatus } from './types';
import { Brand, ErrorNotice, Icon, useResource } from './ui';
import type { IconName } from './ui';

const API_BASE = import.meta.env.VITE_API_BASE || '';
const candidateDesktopCode = desktopLaunchCode(window.location.hash);
const desktopCode = window.location.origin === 'http://127.0.0.1:8000' && !API_BASE ? candidateDesktopCode : null;
if (candidateDesktopCode) window.history.replaceState(null, '', window.location.pathname + window.location.search + '#chat');
type Page = 'images' | 'analytics' | 'roadmap' | 'home' | 'chat' | 'automations' | 'reports' | 'activity' | 'settings' | 'features' | 'commands';
const pages: { key: Page; name: string; icon: IconName; subtitle: string }[] = [
  { key: 'images', name: 'Images', icon: 'spark', subtitle: 'Your private generated images.' },
  { key: 'analytics', name: 'Model analytics', icon: 'activity', subtitle: 'Model performance, response times and issues across tester accounts.' },
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

function Workspace({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const currentPage = () =>
    pages.find((item) => item.key === window.location.hash.slice(1).split('?')[0])?.key || 'chat';
  const [page, updatePage] = useState<Page>(currentPage);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [historyTarget, setHistoryTarget] = useState<HTMLDivElement | null>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const historyTrigger = useRef<HTMLButtonElement>(null);
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
    setMobileSidebarOpen(false);
  };
  const showChat = useCallback(() => {
    updatePage('chat');
    setMobileSidebarOpen(false);
  }, []);
  useEffect(() => {
    if (!mobileSidebarOpen) return;
    const sidebar = sidebarRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    sidebar?.querySelector<HTMLButtonElement>('.mobile-sidebar-close')?.focus();
    const trap = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setMobileSidebarOpen(false); return; }
      if (event.key !== 'Tab' || !sidebar) return;
      const items = [...sidebar.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled)')].filter(item => item.getClientRects().length);
      const first = items[0], last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    window.addEventListener('keydown', trap);
    const desktop = matchMedia('(min-width:701px)');
    const closeOnDesktop = () => { if (desktop.matches) setMobileSidebarOpen(false); };
    desktop.addEventListener('change', closeOnDesktop);
    return () => {
      window.removeEventListener('keydown', trap);
      desktop.removeEventListener('change', closeOnDesktop);
      document.body.style.overflow = previousOverflow;
      if (historyTrigger.current?.getClientRects().length) historyTrigger.current.focus();
      else sidebarRef.current?.querySelector<HTMLButtonElement>('.sidebar-toggle')?.focus();
    };
  }, [mobileSidebarOpen]);
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
  const identity = useResource<{ username: string; email: string; is_admin: boolean; testing_workspace?: boolean }>(api, '/v1/auth/me/', refresh);
  const isAdmin = !identity.error && identity.data?.is_admin === true;
  const testingWorkspace = identity.data?.testing_workspace === true;
  const toolsAvailable = isAdmin && !testingWorkspace;
  const trialAvailable = testingWorkspace && !!identity.data && !identity.error;
  const visiblePrimaryPages: Page[] = toolsAvailable ? primaryPages : trialAvailable ? ['chat', 'images', 'reports', 'home'] : ['chat'];
  useEffect(() => {
    if (identity.data && (!identity.data.is_admin || testingWorkspace) && page !== 'chat' && page !== 'commands' && page !== 'analytics' && !(testingWorkspace && ['images', 'reports', 'home', 'settings', 'activity'].includes(page))) {
      window.location.hash = 'chat';
      updatePage('chat');
    }
  }, [identity.data, page, testingWorkspace]);
  const status = useResource<SystemStatus>(api, '/v1/status/', refresh);
  useEffect(() => {
    if (testingWorkspace || !identity.data) return;
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
  }, [changed, testingWorkspace, identity.data]);
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
  return (
    <div className={`app-shell derek-workspace ${sidebarCollapsed ? 'sidebar-collapsed' : ''} ${mobileSidebarOpen ? 'mobile-sidebar-open' : ''}`}>
      <a className="skip-link" href="#main-content" onClick={(event) => { event.preventDefault(); document.getElementById('main-content')?.focus(); }}>Skip to content</a>
      {mobileSidebarOpen && <div className="sidebar-scrim" onClick={() => setMobileSidebarOpen(false)} aria-hidden="true" />}
      <aside className="sidebar" id="workspace-sidebar" ref={sidebarRef} role={mobileSidebarOpen ? 'dialog' : undefined} aria-modal={mobileSidebarOpen || undefined} aria-label="Workspace and conversations">
        <button className="icon-button mobile-sidebar-close" aria-label="Close conversations" onClick={() => setMobileSidebarOpen(false)}><Icon name="close" /></button>
        <div className="sidebar-brand"><Brand /><button className="icon-button sidebar-toggle" onClick={() => setSidebarCollapsed(!sidebarCollapsed)} aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!sidebarCollapsed}><Icon name="chevron" /></button></div>
        <nav aria-label="Main navigation">{visiblePrimaryPages.map(key => pages.find(item => item.key === key)!).map(item => <button key={item.key} className={`nav-item ${page === item.key ? 'selected' : ''}`} aria-label={item.name} title={sidebarCollapsed ? item.name : undefined} aria-current={page === item.key ? 'page' : undefined} onClick={() => setPage(item.key)}><Icon name={item.icon} /><span>{item.name}</span></button>)}</nav>
        <div className="sidebar-conversations" ref={setHistoryTarget} />
      </aside>
      <div className="profile-control" inert={mobileSidebarOpen}>
        <button className="button profile-trigger" aria-expanded={profileOpen} aria-controls="profile-options" onClick={() => setProfileOpen(!profileOpen)}><span className="avatar">{session.username.slice(0, 1).toUpperCase()}</span><span>Profile</span></button>
        {profileOpen && <div id="profile-options" className="profile-options" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setProfileOpen(false); }}>
          <strong>{identity.data?.username || session.username}</strong>
          {identity.data?.email && <small>{identity.data.email}</small>}
          {isAdmin && <button onClick={() => setPage('analytics')}>Model analytics</button>}
          <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>Appearance · {theme === 'dark' ? 'Switch to light' : 'Switch to dark'}</button>
          <button onClick={() => setPage('commands')}>Request history</button>
          {trialAvailable && <><button onClick={() => setPage('settings')}>Settings</button><button onClick={() => openSettings('Telegram')}>Telegram</button><button onClick={() => openSettings('Browser voice')}>Voice</button><button onClick={() => setPage('activity')}>Activity & notifications</button></>}
          {toolsAvailable && <><button onClick={() => openSettings('Connections')}>Connections & models</button>
          <button onClick={() => openSettings('Desktop voice access')}>Voice</button>
          <button onClick={() => openSettings('Your data')}>Privacy & memory</button>
          <button onClick={() => setPage('activity')}>Activity & notifications</button>
          <button onClick={() => setPage('features')}>Capabilities</button>
          <button onClick={() => setPage('roadmap')}>Build & roadmap</button>
          </>}
          <button disabled={loggingOut} onClick={logout}>Sign out</button>
        </div>}
      </div>
      <main className="main-panel" data-page={page} aria-label={pages.find(item => item.key === page)?.name} id="main-content" tabIndex={-1} inert={mobileSidebarOpen}>
        <header className="topbar topbar-chat">
          <button className="button mobile-history-trigger" ref={historyTrigger} aria-label="Open conversations" aria-expanded={mobileSidebarOpen} aria-controls="workspace-sidebar" onClick={() => { setSidebarCollapsed(false); setMobileSidebarOpen(true); }}><Icon name="chat" size={18} /> History</button>
        </header>
        <div className="page-content">
          <ErrorNotice message={authError || identity.error || status.error} />
          {status.data?.paused && (
            <div className="notice warning">
              <Icon name="pause" size={18} /> Automations are paused. Resume them in Settings when you’re
              ready.
            </div>
          )}
          {page === 'analytics' && (identity.loading ? <p role="status">Checking admin access…</p> : isAdmin ? <Analytics api={api} refresh={refresh} changed={changed} /> : <p role="alert">Admin access is required to view model analytics.</p>)}
          {(toolsAvailable || trialAvailable) && page === 'home' && (
            <Home
              api={api}
              refresh={refresh}
              changed={changed}
              status={status.data}
              username={session.username}
              navigate={destination => setPage(trialAvailable && destination === 'automations' ? 'commands' : destination)}
            />
          )}{' '}
          {page === 'commands' && <Commands api={api} refresh={refresh} changed={changed} />}{' '}
          <div hidden={page !== 'chat'}>
            <div className={`conversation-layout ${todayOpen ? 'today-expanded' : ''}`}><div className="conversation-main"><button hidden={!toolsAvailable && !trialAvailable} className="button today-toggle" aria-expanded={todayOpen} aria-controls="chat-today" onClick={() => setTodayOpen(!todayOpen)}>{todayOpen ? 'Hide Today' : 'Show Today'}</button><Chat
              api={api}
              refresh={refresh}
              changed={changed}
              onAutomations={() => setPage('automations')}
              localVoice={toolsAvailable && status.data?.runtime?.managed}
              toolsEnabled={toolsAvailable}
              audioEnabled={toolsAvailable || trialAvailable}
              testingWorkspace={testingWorkspace}
              active={page === 'chat'}
              historyTarget={historyTarget}
              onNavigateChat={showChat}
            /></div>{(toolsAvailable || trialAvailable) && todayOpen && <aside id="chat-today" className="chat-today" aria-label="Today"><Home api={api} refresh={refresh} changed={changed} status={status.data} username={session.username} navigate={destination => setPage(trialAvailable && destination === 'automations' ? 'commands' : destination)} /></aside>}</div>
          </div>{' '}
          {toolsAvailable && page === 'automations' && <Automations api={api} refresh={refresh} changed={changed} />}{' '}
          {trialAvailable && page === 'images' && <Images api={api} refresh={refresh} changed={changed} />}
          {(toolsAvailable || trialAvailable) && page === 'reports' && <ReportLibrary api={api} refresh={refresh} changed={changed} allowTelegramDelivery={!testingWorkspace} />}{' '}
          {(toolsAvailable || trialAvailable) && page === 'activity' && <Activity api={api} refresh={refresh} changed={changed} />}{' '}
          {toolsAvailable && <div hidden={page !== 'roadmap'}><Roadmap api={api} /></div>}
          {toolsAvailable && page === 'features' && <Features api={api} refresh={refresh} changed={changed} />}{' '}
          {trialAvailable && page === 'settings' && <TrialSettings api={api} refresh={refresh} changed={changed} />}
          {toolsAvailable && page === 'settings' && (
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
      <nav className="bottom-navigation" aria-label="Main navigation" inert={mobileSidebarOpen}>{visiblePrimaryPages.map(key => pages.find(item => item.key === key)!).map(item => <button key={item.key} aria-current={page === item.key ? 'page' : undefined} onClick={() => setPage(item.key)}><Icon name={item.icon} /><span>{item.name}</span></button>)}</nav>
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
