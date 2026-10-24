import { useState } from 'react';
import { Api, errorMessage } from './api';
import { ErrorNotice, Loading, useResource } from './ui';

type Profile = {
  id: string;
  provider: string;
  model: string;
  status: string;
  reason: string;
  privacy: string;
};
type Capability = {
  id: string;
  title: string;
  description: string;
  status: string;
  reason: string;
  location: string;
  approval: string;
  implemented: boolean;
};
const labels: Record<string, string> = {
  ready: 'Ready',
  unverified: 'Needs verification',
  needs_setup: 'Setup needed',
  offline: 'Laptop offline',
  paused: 'Paused',
  temporarily_unavailable: 'Unavailable',
  quota_exhausted: 'Daily limit reached',
  not_implemented: 'Planned',
};

export function Features({ api, refresh, changed }: { api: Api; refresh: number; changed: () => void }) {
  const catalog = useResource<{ profile: Profile; capabilities: Capability[] }>(
    api,
    '/v1/capabilities/',
    refresh,
  );
  const preferences = useResource<{ interactive_profile: string; response_detail: string; profiles: Profile[]; note: string }>(
    api,
    '/v1/preferences/',
    refresh,
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function choose(profile: string, field = 'interactive_profile') {
    setBusy(true);
    setError(null);
    try {
      await api.request('/v1/preferences/', {
        method: 'PATCH',
        body: JSON.stringify({ [field]: profile }),
      });
      changed();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack">
      <section className="panel">
        <h2>How Derek can help</h2>
        <p className="muted">
          Features reflect your connections and laptop availability. Planned features will become available in
          later updates.
        </p>
        <ErrorNotice message={error || catalog.error || preferences.error} />
        {preferences.data && (
          <div className="feature-profile">
            <label>
              Model for new conversations
              <select
                value={preferences.data.interactive_profile}
                disabled={busy}
                onChange={(event) => choose(event.target.value)}
              >
                {preferences.data.profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.id === 'gemini' ? 'Gemini' : 'Current installation'} · {profile.model}
                  </option>
                ))}
              </select>
            </label>
            <p className="muted">{preferences.data.note}</p>
            <label>
              Answer detail across chats
              <select value={preferences.data.response_detail} disabled={busy}
                onChange={(event) => choose(event.target.value, 'response_detail')}>
                <option value="auto">Adaptive · follow the question and recent context</option>
                <option value="brief">Brief</option><option value="balanced">Balanced</option><option value="detailed">Detailed</option>
              </select>
            </label>
            <small>Shared with Telegram and online voice. An explicit request overrides this preference; Telegram keeps each bubble short. You can also use /style in chat.</small>
            <p>{catalog.data?.profile.privacy}</p>
            <small>{catalog.data?.profile.reason}</small>
          </div>
        )}
      </section>
      {catalog.loading && !catalog.data ? (
        <Loading />
      ) : (
        <div className="feature-grid">
          {catalog.data?.capabilities.map((item) => (
            <section className="panel feature-card" key={item.id}>
              <div className="feature-heading">
                <h3>{item.title}</h3>
                <span className={`feature-status feature-${item.status}`}>
                  {labels[item.status] || item.status}
                </span>
              </div>
              <p>{item.description}</p>
              <p className="muted">{item.reason}</p>
              <small>
                {item.location === 'laptop' ? 'Uses your laptop' : 'Uses the assistant service'}
                {item.approval === 'confirm'
                  ? ' · Your confirmation is required'
                  : item.approval.includes('workflow') || item.approval === 'dashboard_activation' || item.approval === 'scope_review'
                    ? ' · Review workflow permissions before activation'
                    : ''}
              </small>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
