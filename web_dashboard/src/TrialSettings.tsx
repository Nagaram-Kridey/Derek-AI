import { useState } from 'react';
import { Api, errorMessage, safeHttpUrl } from './api';
import { MemoryPanel } from './Memory';
import { ErrorNotice, Loading, useResource } from './ui';

type LinkState = { configured: boolean; connected: boolean; username?: string };
type Preferences = { response_detail: string };

export function TrialSettings({ api, refresh, changed }: { api: Api; refresh: number; changed: () => void }) {
  const preferences = useResource<Preferences>(api, '/v1/preferences/', refresh);
  const telegram = useResource<LinkState>(api, '/v1/telegram/link/', refresh);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [connectUrl, setConnectUrl] = useState('');
  const [expires, setExpires] = useState('');
  async function perform(action: () => Promise<unknown>) {
    setBusy(true); setError(null);
    try { await action(); changed(); } catch (failure) { setError(errorMessage(failure)); } finally { setBusy(false); }
  }
  return <div className="stack trial-settings">
    <ErrorNotice message={error || preferences.error || telegram.error} />
    <section className="panel stack">
      <h2>Preferences</h2>
      {!preferences.data && !preferences.error ? <Loading /> : <label>Answer detail
        <select aria-label="Answer detail" value={preferences.data?.response_detail || 'auto'} disabled={busy || !preferences.data} onChange={event => void perform(() => api.request('/v1/preferences/', { method: 'PATCH', body: JSON.stringify({ response_detail: event.target.value }) }))}>
          <option value="auto">Automatic</option><option value="brief">Brief</option><option value="balanced">Balanced</option><option value="detailed">Detailed</option>
        </select>
      </label>}
    </section>
    <section className="panel stack">
      <div><h2>Telegram</h2><p className="muted">Connect your own private Telegram chat. Your connection is separate from other accounts.</p></div>
      {!telegram.data && !telegram.error ? <Loading /> : !telegram.data?.configured ? <p className="muted">The test administrator has not configured the Telegram bot yet.</p> : <>
        <p>{telegram.data.connected ? `Connected${telegram.data.username ? ' as ' + telegram.data.username : ''}.` : 'Not connected.'}</p>
        <div className="actions">
          {!telegram.data.connected && <button className="button" disabled={busy} onClick={() => void perform(async () => {
            const result = await api.post<{ url: string; expires_at: string }>('/v1/telegram/link/');
            const url = safeHttpUrl(result.url);
            if (!url || new URL(url).hostname !== 't.me') throw new Error('The service returned an invalid Telegram link.');
            setConnectUrl(url); setExpires(result.expires_at);
          })}>Connect Telegram</button>}
          <button className="button secondary" disabled={busy} onClick={changed}>Refresh connection</button>
          {telegram.data.connected && <button className="button secondary" disabled={busy} onClick={() => void perform(async () => { await api.delete('/v1/telegram/link/'); setConnectUrl(''); })}>Disconnect</button>}
        </div>
        {!telegram.data.connected && connectUrl && <div><a className="button" href={connectUrl} target="_blank" rel="noreferrer">Open Telegram to connect</a><p className="muted">Open the link and press Start, then refresh this connection. Link expires {new Date(expires).toLocaleTimeString()}.</p></div>}
      </>}
    </section>
    <section className="panel stack"><h2>Browser voice</h2><p className="muted">Use the microphone in Chat to record a voice note, or upload an audio file. Review it before sending. Your browser will ask for microphone permission; voice notes are transcribed by the service.</p><p className="muted">Microphone recording needs HTTPS and a supported browser. If recording is unavailable, upload audio or type your message.</p></section>
    <MemoryPanel api={api} refresh={refresh} changed={changed} />
  </div>;
}
