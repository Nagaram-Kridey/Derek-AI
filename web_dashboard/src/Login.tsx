import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Api, ApiError, errorMessage } from './api';
import { Brand, ErrorNotice, Icon } from './ui';
import './login.css';

export type Session = {
  token: string;
  username: string;
  remember?: boolean;
  email?: string;
  is_admin?: boolean;
  auth_provider?: string;
};

type GoogleIdentity = {
  initialize: (options: {
    client_id: string;
    nonce: string;
    auto_select: boolean;
    callback: (response: { credential: string }) => void;
  }) => void;
  renderButton: (element: HTMLElement, options: {
    theme: string; size: string; text: string; shape: string; width: number;
  }) => void;
  cancel: () => void;
};

const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');
const GOOGLE_SCRIPT = 'https://accounts.google.com/gsi/client';
let googleScript: Promise<GoogleIdentity> | undefined;

function googleIdentity(): GoogleIdentity | undefined {
  return (window as Window & { google?: { accounts?: { id?: GoogleIdentity } } }).google?.accounts?.id;
}

function loadGoogle(): Promise<GoogleIdentity> {
  const ready = googleIdentity();
  if (ready) return Promise.resolve(ready);
  if (googleScript) return googleScript;
  googleScript = new Promise<GoogleIdentity>((resolve, reject) => {
    let script = document.querySelector<HTMLScriptElement>(`script[src="${GOOGLE_SCRIPT}"]`);
    if (!script) {
      script = document.createElement('script');
      script.src = GOOGLE_SCRIPT;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
    const node = script;
    const finish = (error?: Error) => {
      window.clearTimeout(timeout);
      node.removeEventListener('load', loaded);
      node.removeEventListener('error', failed);
      const identity = googleIdentity();
      if (!error && identity) resolve(identity);
      else {
        node.remove();
        reject(error || new Error('Google sign-in could not load. Please try again.'));
      }
    };
    const loaded = () => finish();
    const failed = () => finish(new Error('Google sign-in could not load. Check your connection or browser settings, then retry.'));
    const timeout = window.setTimeout(failed, 15000);
    node.addEventListener('load', loaded);
    node.addEventListener('error', failed);
  }).catch(error => {
    googleScript = undefined;
    throw error;
  });
  return googleScript;
}

// The nonce challenge is bound to an HttpOnly API cookie, including when an
// explicitly configured API lives on a different origin.
async function googleRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include',
    redirect: 'error',
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
  });
  const data = await response.json();
  if (!response.ok) throw new ApiError(typeof data.detail === 'string' ? data.detail : 'Google sign-in could not complete. Please retry.', response.status);
  return data as T;
}

export function Login({ onLogin, notice }: { onLogin: (session: Session) => void; notice?: string }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(notice || null);
  const [busy, setBusy] = useState(false);
  const [remember, setRemember] = useState(false);
  const [googleStatus, setGoogleStatus] = useState<'loading' | 'ready' | 'disabled' | 'error'>('loading');
  const [testingWorkspace, setTestingWorkspace] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const googleButton = useRef<HTMLDivElement>(null);
  const signingIn = useRef(false);
  const latest = useRef({ onLogin, remember });
  latest.current = { onLogin, remember };

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const setupTimeout = window.setTimeout(() => controller.abort(), 30000);
    let identity: GoogleIdentity | undefined;
    setGoogleStatus('loading');
    async function setup() {
      try {
        const config = await googleRequest<{ google_enabled: boolean; google_client_id: string; testing_workspace?: boolean }>('/v1/auth/config/', { signal: controller.signal });
        if (!active) return;
        setTestingWorkspace(config.testing_workspace === true);
        if (!config.google_enabled || !config.google_client_id) {
          setGoogleStatus('disabled');
          return;
        }
        identity = await loadGoogle();
        if (!active) return;
        const challenge = await googleRequest<{ nonce: string; challenge_id: string }>('/v1/auth/google/challenge/', { method: 'POST', signal: controller.signal });
        if (!active || !googleButton.current) return;
        identity.initialize({
          client_id: config.google_client_id,
          nonce: challenge.nonce,
          auto_select: false,
          callback: response => {
            if (!active || signingIn.current) return;
            signingIn.current = true;
            setBusy(true);
            setError(null);
            void googleRequest<Session>('/v1/auth/google/', {
              method: 'POST',
              body: JSON.stringify({ credential: response.credential, challenge_id: challenge.challenge_id }),
              signal: AbortSignal.timeout(30000),
            }).then(session => {
              if (active) latest.current.onLogin({ ...session, remember: latest.current.remember });
            }).catch(failure => {
              if (active) {
                setError(errorMessage(failure));
                // A challenge may have been consumed even on a failed exchange.
                setAttempt(value => value + 1);
              }
            }).finally(() => {
              signingIn.current = false;
              if (active) setBusy(false);
            });
          },
        });
        googleButton.current.replaceChildren();
        identity.renderButton(googleButton.current, {
          theme: 'outline', size: 'large', text: 'continue_with', shape: 'rectangular',
          width: Math.min(360, Math.floor(googleButton.current.parentElement?.clientWidth || 280)),
        });
        setGoogleStatus('ready');
      } catch (failure) {
        if (active) {
          setGoogleStatus('error');
          setError(controller.signal.aborted ? 'Google sign-in took too long to load. Please retry.' : errorMessage(failure));
        }
      } finally {
        window.clearTimeout(setupTimeout);
      }
    }
    void setup();
    return () => {
      active = false;
      window.clearTimeout(setupTimeout);
      controller.abort();
      identity?.cancel();
    };
  }, [attempt]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (signingIn.current) return;
    signingIn.current = true;
    setBusy(true);
    setError(null);
    try {
      onLogin({ ...(await new Api('', API_BASE).post<Session>('/v1/auth/login', { username, password })), remember });
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      signingIn.current = false;
      setBusy(false);
    }
  }

  return <main className="login-layout">
    <section className="login-story">
      <Brand />
      <div>
        <span className="eyebrow light">A PERSONAL ASSISTANT. A LITTLE POSSIBILITY.</span>
        <h1>Your day,<br />a little lighter.</h1>
        <p>Space to think. Help to get things done.<br />Meet your everyday companion.</p>
      </div>
      <div className="orbit-art" aria-hidden="true">
        <div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" /><div className="orbit-ring ring-three" />
        <span className="orbit-center"><Icon name="spark" size={60} /></span><span className="orbit-dot" />
      </div>
      <span className="story-footer">DEREK <span>THOUGHTFULLY AT YOUR SIDE</span></span>
    </section>
    <section className="login-panel">
      <div className="login-box">
        <span className="eyebrow">YOUR PERSONAL WORKSPACE</span>
        <h2>{testingWorkspace ? 'Testing workspace' : 'Welcome home.'}</h2>
        <p className="muted">Continue with Google to create your account or sign in.</p>
        <div className="google-signin" aria-busy={busy || googleStatus === 'loading'}>
          <div ref={googleButton} className="google-signin-button" inert={busy} hidden={googleStatus !== 'ready'} />
          <div role="status" aria-live="polite">
            {busy ? 'Signing in…' : googleStatus === 'loading' ? 'Preparing Google sign-in…' : googleStatus === 'disabled' ? 'Google sign-in is not configured yet. Ask the admin to enable it.' : null}
          </div>
          {googleStatus === 'error' && <button className="button secondary full" onClick={() => { setError(null); setAttempt(value => value + 1); }}>Retry Google sign-in</button>}
        </div>
        <label className="checkbox-label remember-option">
          <input type="checkbox" checked={remember} onChange={event => setRemember(event.target.checked)} disabled={busy} />
          Keep me signed in on this browser
        </label>
        <ErrorNotice message={error} />
        <p className="login-note">{testingWorkspace ? 'Sign in with Google to join this limited trial. Chats are saved and sent to the configured model provider.' : 'Your conversations and saved work stay in your own account.'}</p>
        <details className="admin-signin">
          <summary>Admin sign in</summary>
          <form onSubmit={submit}>
            <label>Username<input autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} required disabled={busy} /></label>
            <label>Password<input type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required disabled={busy} /></label>
            <button className="button primary full" disabled={busy}>{busy ? 'Signing in…' : 'Enter admin workspace'}<Icon name="arrow" size={18} /></button>
          </form>
        </details>
      </div>
    </section>
  </main>;
}
