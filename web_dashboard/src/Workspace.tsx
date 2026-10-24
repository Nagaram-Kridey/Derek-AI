import { useState } from 'react';
import { Api, errorMessage, safeHttpUrl } from './api';
import { MemoryPanel } from './Memory';
import type { CalendarEvent, Device, SystemStatus } from './types';
import { Badge, ErrorNotice, Icon, JsonDetails, dateLabel, useResource } from './ui';

export function Settings({
  api,
  refresh,
  changed,
  status,
}: {
  api: Api;
  refresh: number;
  changed: () => void;
  status: SystemStatus | null;
}) {
  const devices = useResource<Device[]>(api, '/v1/devices/', refresh);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [credential, setCredential] = useState('');
  const [name, setName] = useState('Windows companion');
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [showVoiceToken, setShowVoiceToken] = useState(false);
  async function perform(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      changed();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  function integrationReady(value: unknown) {
    if (typeof value === 'boolean') return value;
    if (value && typeof value === 'object')
      return (
        (value as { connected?: boolean; configured?: boolean }).connected ??
        (value as { configured?: boolean }).configured
      );
    return false;
  }
  return (
    <div className="stack">
      <ErrorNotice message={error || devices.error} />
      <MemoryPanel api={api} refresh={refresh} changed={changed} />
      {status?.runtime?.managed && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">ON THIS LAPTOP</span>
              <h2>Your local app</h2>
            </div>
            <Badge status="running locally" />
          </div>
          <p className="muted">{status.runtime.note}</p>
          <div className="list-row"><strong>Local supervisor</strong><Badge status={status.runtime.supervisor_status || 'unknown'} /></div>
          {Object.entries(status.runtime.issues || {}).map(([component, category]) => <p className="error-text" key={component}>{component.replaceAll('_', ' ')} needs attention ({category}). Other healthy services continue running.</p>)}
          <div className="list-row">
            <div>
              <strong>Start at Windows sign-in</strong>
              <p className="muted">Start quietly in the tray. Voice stays muted until you choose Listen.</p>
            </div>
            <button
              className="button secondary small"
              disabled={busy || typeof status.runtime.start_at_login !== 'boolean'}
              onClick={() => {
                const enabled = status.runtime?.start_at_login;
                if (typeof enabled !== 'boolean') return;
                void perform(() => api.post('/v1/local/startup/', { enabled: !enabled }));
              }}
            >
              {typeof status.runtime.start_at_login !== 'boolean'
                ? 'Checking…'
                : status.runtime.start_at_login
                  ? 'Turn off'
                  : 'Turn on'}
            </button>
          </div>
          <div className="list-row">
            <div>
              <strong>Voice shortcut</strong>
              <p className="muted">
                {status.runtime.voice_shortcut
                  ? `${status.runtime.voice_shortcut} opens or focuses the voice window. Choose Listen to arm capture.`
                  : 'Open voice from the tray. The shortcut may be in use by another application.'}
              </p>
            </div>
            <div className="actions">
              <button
                className="button secondary small"
                disabled={busy}
                onClick={() => perform(() => api.post('/v1/local/voice/', { mode: 'online' }))}
              >
                Open voice
              </button>
              <button
                className="button secondary small"
                disabled={busy}
                onClick={() => perform(() => api.post('/v1/local/voice/', { mode: 'private' }))}
              >
                Private voice
              </button>
            </div>
          </div>
          <div className="list-row">
            <div>
              <strong>Local recovery backup</strong>
              <p className="muted">
                {status.runtime.backup?.created_at
                  ? `${dateLabel(status.runtime.backup.created_at)} · ${status.runtime.backup.encrypted ? 'Encrypted with your existing credential key' : 'Local file copy'}`
                  : 'The launcher will create a snapshot shortly.'}
              </p>
              <small>
                {status.runtime.backup?.format === 1 ? 'Normal assistant database and referenced reports. Private local chat and browser sessions are excluded.' : 'Legacy database snapshot; report files and private local chat are separate.'} This is not an off-device backup.
              </small>
              {status.runtime.backup?.verified && <p className="muted">Isolated restore verified · {status.runtime.backup.files} files checked. No restored jobs were started.</p>}
              {status.runtime.backup?.reason && <p className="error-text">{status.runtime.backup.reason}</p>}
            </div>
            <Badge status={status.runtime.backup?.status || 'pending'} />
          </div>
          <div className="list-row"><div><strong>Screen observation</strong><p className="muted">Open a local consent window to preview one app’s accessible controls. No screenshots, model uploads or mouse input.</p></div><button className="button secondary small" disabled={busy || status.runtime.supervisor_status !== 'running'} onClick={() => perform(() => api.post('/v1/local/screen/',{}))}>Open local preview</button></div>
        </section>
      )}
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Automation controls</h2>
            <p className="muted">
              Pausing prevents new actions. A request already sent to another service may finish.
            </p>
          </div>
          <button
            className="button primary"
            disabled={busy || !status}
            onClick={() => perform(() => api.post('/v1/control/pause/', { paused: !status?.paused }))}
          >
            <Icon name={status?.paused ? 'play' : 'pause'} />
            {status?.paused ? 'Resume automations' : 'Pause all'}
          </button>
        </div>
        <p className="muted">
          Scheduler:{' '}
          {status?.scheduler_online
            ? 'online'
            : status?.runtime?.managed
              ? 'waiting for the local scheduler to recover'
              : 'offline — start the worker and scheduler for background jobs'}
        </p>
        <JsonDetails value={status?.usage} label="Daily usage and configured limits" />
      </section>
      <section className="panel">
        <h2>Connections</h2>
        {status?.language_model && (
          <p className="muted">
            Chat / tool selection: {status.language_model.model} ({status.language_model.provider}).
            {status.language_model.research_model && <> Research planning / verification / reports: {status.language_model.research_model}.</>}
            {' '}Search: {status.language_model.web_search}. Choose the model for new conversations on the Features
            page. Local generation requires Ollama and enough free RAM on the service PC.
          </p>
        )}
        <div className="card-grid">
          {Object.entries(status?.integrations || {}).map(([key, value]) => (
            <div className="connection-tile" key={key}>
              <strong>
                {key === 'gemini'
                  ? 'Gemini'
                  : key === 'ollama'
                    ? 'Ollama (local)'
                    : key === 'freellmapi'
                      ? 'FreeLLMAPI router'
                    : key === 'cartesia'
                      ? 'Speech'
                      : key === 'calendar'
                        ? 'Google Calendar'
                        : 'Telegram'}
              </strong>
              <Badge
                status={
                  integrationReady(value) ? (key === 'calendar' ? 'connected' : 'configured') : 'setup needed'
                }
              />
            </div>
          ))}
        </div>
        <p className="muted">
          API keys are configured on the service host. Connect your Calendar account here after OAuth has been
          configured.
        </p>
        <div className="actions">
          <button
            className="button secondary"
            disabled={busy}
            onClick={() =>
              perform(async () => {
                const result = await api.post<{ url: string }>('/v1/calendar/connect/');
                const url = safeHttpUrl(result.url);
                if (!url) throw new Error('Invalid authorization URL');
                window.location.assign(url);
              })
            }
          >
            Connect Google Calendar
          </button>
          <button
            className="button secondary"
            disabled={busy}
            onClick={() =>
              perform(async () => {
                const data = await api.request<CalendarEvent[]>('/v1/calendar/events/');
                setEvents(data);
              })
            }
          >
            Upcoming events
          </button>
          <button
            className="text-button"
            disabled={busy}
            onClick={() => perform(() => api.delete('/v1/calendar/events/'))}
          >
            Disconnect Calendar
          </button>
        </div>
        {events.map((event) => (
          <div className="list-row" key={event.id}>
            <strong>{event.summary || 'Untitled event'}</strong>
            <span>{dateLabel(event.start?.dateTime || event.start?.date)}</span>
          </div>
        ))}
      </section>
      <section className="panel">
        <h2>Desktop companion</h2>
        <p className="muted">
          Pair your Windows computer. The device credential is displayed once. Put it in the companion
          environment configuration.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void perform(async () => {
              const device = await api.post<Device>('/v1/devices/', { name });
              setCredential(device.credential || '');
            });
          }}
          className="pair-form"
        >
          <label>
            Device name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <button className="button secondary" disabled={busy}>
            Pair device
          </button>
        </form>
        {credential && (
          <div className="notice warning">
            <p>Copy this credential now:</p>
            <code className="credential">{credential}</code>
            <button className="text-button" onClick={() => setCredential('')}>
              Hide credential
            </button>
          </div>
        )}
        {devices.data?.map((device) => (
          <div className="list-row" key={device.id}>
            <div>
              <strong>{device.name}</strong>
              <p className="muted">Last seen {dateLabel(device.last_seen_at)}</p>
            </div>
            <button
              className="text-button"
              disabled={busy}
              onClick={() => {
                if (window.confirm('Revoke this device credential?'))
                  void perform(() => api.delete(`/v1/devices/${device.id}/`));
              }}
            >
              Revoke
            </button>
          </div>
        ))}
      </section>
      <section className="panel">
        <h2>Desktop voice access</h2>
        <p className="muted">
          Signing in to the local app refreshes online voice access in Windows Credential Manager. Signing out
          revokes that access until you sign in again. Private local voice uses Ollama without this account
          token.
        </p>
        <p className="muted">
          Advanced setup: reveal the token only when configuring a separate trusted client.
        </p>
        <button className="button secondary" onClick={() => setShowVoiceToken(!showVoiceToken)}>
          {showVoiceToken ? 'Hide token' : 'Show voice token'}
        </button>
        {showVoiceToken && <code className="credential">{api.token}</code>}
      </section>
      <section className="panel">
        <h2>Your data</h2>
        <p className="muted">
          History stays until you delete it. Individual tasks, workflows and reports can be deleted from their
          pages.
        </p>
        <div className="actions">
          <button
            className="button secondary"
            disabled={busy}
            onClick={() => perform(() => api.download('/v1/export/', 'derek-export.json'))}
          >
            Export my data
          </button>
          <button
            className="button danger"
            disabled={busy}
            onClick={() => {
              if (window.confirm('Permanently delete all conversation history?'))
                void perform(() => api.delete('/v1/history/'));
            }}
          >
            Delete conversation history
          </button>
        </div>
      </section>
    </div>
  );
}
