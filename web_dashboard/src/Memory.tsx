import { useState } from 'react';
import type { FormEvent } from 'react';
import { Api, errorMessage } from './api';
import { ErrorNotice, dateLabel, useResource } from './ui';

type Memory = {
  id: string; title: string; content: string; status: 'active' | 'suggested';
  pinned: boolean; version: number; source_message_id: number | null;
  updated_at: string;
};
type MemoryState = { enabled: boolean; suggestions_enabled: boolean; memories: Memory[] };

export function MemoryPanel({ api, refresh, changed }: { api: Api; refresh: number; changed: () => void }) {
  const resource = useResource<MemoryState>(api, '/v1/memories/', refresh);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const [editing, setEditing] = useState<Memory | null>(null);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [pinned, setPinned] = useState(false);
  const [shown, setShown] = useState(10);
  const state = resource.data;
  async function perform(action: () => Promise<unknown>) {
    setBusy(true); setError(null); setNotice('');
    try { await action(); changed(); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  function reset() { setEditing(null); setTitle(''); setContent(''); setPinned(false); }
  async function save(event: FormEvent) {
    event.preventDefault();
    await perform(async () => {
      await api.request(editing ? `/v1/memories/${editing.id}/` : '/v1/memories/', {
        method: editing ? 'PATCH' : 'POST',
        body: JSON.stringify({ title, content, pinned, ...(editing ? { version: editing.version } : {}) }),
      });
      reset();
    });
  }
  return <section className="panel stack" aria-label="Shared memory">
    <div className="section-heading"><div><h2>Memory</h2>
      <p className="muted">Useful details shared across web, Telegram and online voice. Private chat stays separate.</p>
    </div><span className="pill">{state?.enabled ? 'On' : 'Paused'}</span></div>
    <ErrorNotice message={error || resource.error} />
    {notice && <p role="status">{notice}</p>}
    {state && <div className="stack">
      <label><input type="checkbox" checked={state.enabled} disabled={busy}
        onChange={() => perform(() => api.request('/v1/memories/', { method: 'PATCH', body: JSON.stringify({ enabled: !state.enabled }) }))} /> Use shared memory in new replies</label>
      <label><input type="checkbox" checked={state.suggestions_enabled} disabled={busy}
        onChange={() => perform(() => api.request('/v1/memories/', { method: 'PATCH', body: JSON.stringify({ suggestions_enabled: !state.suggestions_enabled }) }))} /> Suggest clear preferences and profile details for review</label>
    </div>}
    <p className="muted">Say “Remember that I prefer concise replies” or “Remember Project: Derek”. Suggestions are used only after you accept them. Relevant accepted details may be sent to your selected model provider. Changes apply to future turns.</p>
    <form onSubmit={save} className="stack">
      <h3>{editing ? 'Edit memory' : 'Add a detail'}</h3>
      <label>Label<input value={title} maxLength={80} required disabled={busy} onChange={e => setTitle(e.target.value)} placeholder="Project" /></label>
      <label>Detail<textarea value={content} maxLength={400} required disabled={busy} onChange={e => setContent(e.target.value)} placeholder="I am building Derek as my personal assistant." /></label>
      <label><input type="checkbox" checked={pinned} disabled={busy} onChange={e => setPinned(e.target.checked)} /> Keep broadly useful across conversations</label>
      <div className="button-row"><button className="button primary" disabled={busy || !state?.enabled}>Save memory</button>
        {editing && <button type="button" className="button secondary" onClick={reset} disabled={busy}>Cancel edit</button>}</div>
    </form>
    <div><button className="button secondary" disabled={busy || !state?.suggestions_enabled}
      onClick={() => perform(async () => {
        const result = await api.post<{ suggestions_added: number }>('/v1/memories/scan/', {});
        setNotice(`Added ${result.suggestions_added} suggestions from up to 500 recent user messages. Nothing was automatically accepted.`);
      })}>Find details in previous chats</button></div>
    {(['active', 'suggested'] as const).map(status => {
      const rows = (state?.memories || []).filter(row => row.status === status);
      return <div className="stack" key={status}><h3>{status === 'active' ? 'Accepted details' : 'Suggestions to review'} · {rows.length}</h3>
        {!rows.length && <p className="muted">{status === 'active' ? 'No accepted details yet.' : 'No suggestions waiting.'}</p>}
        {rows.slice(0, shown).map(row => <article className="list-row" key={row.id}>
          <div><strong>{row.title}</strong><p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{row.content}</p>
            <small>{row.source_message_id ? 'From your chat' : 'Added directly'} · {dateLabel(row.updated_at)}{row.pinned ? ' · Broadly useful' : ''}</small></div>
          <div className="button-row">
            {status === 'suggested' && <button className="button primary small" disabled={busy || !state?.enabled}
              onClick={() => perform(() => api.request(`/v1/memories/${row.id}/`, { method: 'PATCH', body: JSON.stringify({ version: row.version, status: 'active' }) }))}>Accept</button>}
            <button className="button secondary small" disabled={busy} onClick={() => { setEditing(row); setTitle(row.title); setContent(row.content); setPinned(row.pinned); }}>Edit</button>
            <button className="button secondary small" disabled={busy} onClick={() => {
              if (window.confirm(`Forget “${row.title}” from shared memory? Existing chats and backups remain separate.`))
                perform(async () => { await api.request(`/v1/memories/${row.id}/`, { method: 'DELETE', body: JSON.stringify({ version: row.version }) }); if (editing?.id === row.id) reset(); });
            }}>Forget</button>
          </div>
        </article>)}
        {rows.length > shown && <button className="button secondary small" disabled={busy} onClick={() => setShown(shown + 20)}>Show more</button>}
      </div>;
    })}
    <small>Memory lookup runs locally without another model call. Up to five relevant details are added to a reply. History export includes memories; deleting all assistant history also clears shared memory. Forgetting does not erase old transcripts, model-provider records or backups.</small>
  </section>;
}
