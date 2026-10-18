import { useState } from 'react';
import { Api, errorMessage } from './api';
import type { Audit, Notification } from './types';
import { Badge, Empty, ErrorNotice, Icon, JsonDetails, Loading, dateLabel, useResource } from './ui';

const names: Record<string, string> = {
  'command.queued': 'Request saved',
  'command.running': 'Request started',
  'command.finished': 'Request finished',
  'command.cancelled': 'Response stopped',
  'action.decided': 'Action reviewed',
  'task.created': 'Routine created',
  'task.updated': 'Routine updated',
  'task.pause': 'Routine paused',
  'task.resume': 'Routine resumed',
  'schedule.dispatched': 'Scheduled task dispatched',
  'report.queued': 'Research saved',
  'report.failed': 'Research needs attention',
  'report.cancelled': 'Research stopped',
  'notification.delivery': 'Update delivery',
  'command.delivery': 'Reply delivery',
  'workflow.enabled': 'Workflow enabled',
  'workflow.paused': 'Workflow paused',
  'workflow.drafted': 'Workflow drafted',
  'workflow.edited': 'Workflow edited',
  'run.step_completed': 'Workflow step finished',
  'run.needs_attention': 'Workflow needs attention',
  'auth.login': 'Signed in',
  'control.pause': 'Automation controls changed',
};

export function Activity({ api, refresh, changed }: { api: Api; refresh: number; changed: () => void }) {
  const audit = useResource<Audit[]>(api, '/v1/audit/', refresh);
  const notifications = useResource<Notification[]>(api, '/v1/notifications/', refresh);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  async function markRead(id?: string) {
    setBusy(true);
    setError(null);
    try {
      await api.post(id ? `/v1/notifications/${id}/read/` : '/v1/notifications/');
      changed();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  const unread = notifications.data?.filter((item) => !item.read_at).length || 0;
  const visible =
    audit.data?.filter(
      (item) =>
        (filter === 'all' ||
          (filter === 'attention'
            ? /fail|attention|cancelled/.test(item.action)
            : item.action.startsWith(filter))) &&
        (names[item.action] || item.action).toLowerCase().includes(search.toLowerCase()),
    ) || [];
  return (
    <div className="stack">
      <section className="panel">
        <div className="section-heading">
          <div>
            <span className="eyebrow">FROM DEREK</span>
            <h2>Your updates</h2>
          </div>
          {unread > 0 && (
            <button className="button secondary small" disabled={busy} onClick={() => markRead()}>
              Mark all {unread} read
            </button>
          )}
        </div>
        <ErrorNotice message={error || notifications.error} />
        {notifications.loading && !notifications.data ? (
          <Loading />
        ) : notifications.data?.length ? (
          notifications.data.map((item) => (
            <div className={`list-row notification-row ${!item.read_at ? 'unread' : ''}`} key={item.id}>
              <div>
                <p>{item.text}</p>
                <small>{dateLabel(item.created_at)}</small>
                {item.error && <p className="error-text">{item.error}</p>}
              </div>
              <div className="actions">
                <Badge status={item.status === 'in_app' ? 'in your updates' : item.status} />
                {!item.read_at && (
                  <button className="text-button" disabled={busy} onClick={() => markRead(item.id)}>
                    Mark read
                  </button>
                )}
              </div>
            </div>
          ))
        ) : (
          <Empty icon="spark" title="You're all caught up">
            Reminders and finished research will appear here.
          </Empty>
        )}
      </section>
      <section className="panel">
        <div className="section-heading">
          <div>
            <span className="eyebrow">A CLEAR RECORD</span>
            <h2>Execution history</h2>
          </div>
          <Icon name="activity" size={26} />
        </div>
        <div className="filter-bar">
          <input
            type="search"
            aria-label="Search activity"
            placeholder="Find an activity…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select value={filter} aria-label="Filter activity" onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All activity</option>
            <option value="command">Conversations</option>
            <option value="task">Routines</option>
            <option value="workflow">Workflows</option>
            <option value="report">Research</option>
            <option value="attention">Needs attention / stopped</option>
          </select>
        </div>
        <ErrorNotice message={audit.error} />
        {audit.loading && !audit.data ? (
          <Loading />
        ) : visible.length ? (
          visible.map((item) => (
            <div className="list-row audit-row" key={item.id}>
              <span className="tile-icon">
                <Icon
                  name={
                    item.action.startsWith('report')
                      ? 'file'
                      : item.action.startsWith('task') || item.action.startsWith('schedule')
                        ? 'clock'
                        : 'activity'
                  }
                  size={16}
                />
              </span>
              <div>
                <strong>
                  {names[item.action] || item.action.replaceAll('.', ' · ').replaceAll('_', ' ')}
                </strong>
                <p className="muted">{dateLabel(item.created_at)}</p>
                <JsonDetails value={item.details || item.metadata} label="Saved details" />
              </div>
            </div>
          ))
        ) : (
          <Empty icon="activity" title="No activity in this view">
            Saved requests and workflow outcomes will appear here.
          </Empty>
        )}
      </section>
    </div>
  );
}
