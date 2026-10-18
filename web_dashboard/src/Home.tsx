import { useState } from 'react';
import { Api, errorMessage } from './api';
import type { CommandResult, Notification, Report, ScheduledTask, SystemStatus } from './types';
import { Badge, Empty, ErrorNotice, Icon, Loading, dateLabel, useResource } from './ui';
import { scheduleLabel } from './schedules';

type Destination = 'chat' | 'automations' | 'reports' | 'activity' | 'features' | 'settings' | 'commands';

export function Home({
  api,
  refresh,
  changed,
  status,
  username,
  navigate,
}: {
  api: Api;
  refresh: number;
  changed: () => void;
  status: SystemStatus | null;
  username: string;
  navigate: (page: Destination) => void;
}) {
  const tasks = useResource<ScheduledTask[]>(api, '/v1/tasks/', refresh);
  const reports = useResource<Report[]>(api, '/v1/reports/', refresh);
  const commands = useResource<CommandResult[]>(api, '/v1/commands/?active=true', refresh);
  const notifications = useResource<Notification[]>(api, '/v1/notifications/', refresh);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const upcoming =
    tasks.data
      ?.filter((task) => task.enabled && task.next_run_at)
      .sort((a, b) => Date.parse(a.next_run_at!) - Date.parse(b.next_run_at!))
      .slice(0, 4) || [];
  const unread = notifications.data?.filter((item) => !item.read_at) || [];
  const active =
    commands.data?.filter((item) => ['queued', 'running', 'awaiting_confirmation'].includes(item.status)) ||
    [];
  const hour = Number(
    new Intl.DateTimeFormat('en-IN', { hour: 'numeric', hourCycle: 'h23', timeZone: 'Asia/Kolkata' }).format(
      new Date(),
    ),
  );
  async function markRead() {
    setBusy(true);
    setError(null);
    try {
      await api.post('/v1/notifications/');
      changed();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack home-page">
      <section className="day-hero">
        <div>
          <span className="eyebrow">YOUR DAY, WITH A LITTLE MORE SPACE</span>
          <h2>
            Good {hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening'}, {username}.
          </h2>
          <p>Pick up a thought, check a routine, or let Derek help with what comes next.</p>
          <button className="button primary" onClick={() => navigate('chat')}>
            Talk to Derek
            <Icon name="arrow" size={16} />
          </button>
        </div>
        <div className="hero-symbol" aria-hidden="true">
          <Icon name="spark" size={70} />
        </div>
      </section>
      <ErrorNotice message={error || tasks.error || reports.error || commands.error || notifications.error} />
      <div className="stat-grid">
        <button className="stat-card" onClick={() => navigate('automations')}>
          <Icon name="clock" />
          <strong>{tasks.data?.filter((task) => task.enabled).length ?? '—'}</strong>
          <span>Active routines</span>
        </button>
        <button className="stat-card" onClick={() => navigate('commands')}>
          <Icon name="chat" />
          <strong>{active.length}</strong>
          <span>In progress / review</span>
        </button>
        <button className="stat-card" onClick={() => navigate('reports')}>
          <Icon name="file" />
          <strong>{reports.data?.filter((item) => item.status === 'completed').length ?? '—'}</strong>
          <span>Finished reports</span>
        </button>
        <button className="stat-card" onClick={() => navigate('activity')}>
          <Icon name="activity" />
          <strong>{unread.length}</strong>
          <span>Unread updates</span>
        </button>
      </div>
      {status?.runtime?.stopping && (
        <div className="notice warning" role="status">
          Derek is finishing current work before stopping or restarting. New requests will stay saved until
          the next start.
        </div>
      )}
      {status?.paused && (
        <div className="notice warning">
          Automations are paused. You can still chat and review saved work.{' '}
          <button className="text-button" onClick={() => navigate('settings')}>
            Open controls
          </button>
        </div>
      )}
      <div className="home-grid">
        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">ON THE HORIZON</span>
              <h3>Next up</h3>
            </div>
            <button className="text-button" onClick={() => navigate('automations')}>
              Manage routines
              <Icon name="chevron" size={12} />
            </button>
          </div>
          {tasks.loading && !tasks.data ? (
            <Loading />
          ) : upcoming.length ? (
            upcoming.map((task) => (
              <div className="upcoming-row" key={task.id}>
                <span className="tile-icon">
                  <Icon name={task.kind === 'research' ? 'file' : 'clock'} size={18} />
                </span>
                <div>
                  <strong>{task.name}</strong>
                  <p className="muted">{scheduleLabel(task.schedule)}</p>
                  <small>{dateLabel(task.next_run_at)}</small>
                </div>
              </div>
            ))
          ) : (
            <Empty icon="clock" title="A little room in your schedule">
              Create a reminder or a recurring task when you need one.
            </Empty>
          )}
        </section>
        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">FROM YOUR ASSISTANT</span>
              <h3>Latest updates</h3>
            </div>
            {!!unread.length && (
              <button className="text-button" disabled={busy} onClick={markRead}>
                Mark all read
              </button>
            )}
          </div>
          {notifications.loading && !notifications.data ? (
            <Loading />
          ) : notifications.data?.length ? (
            notifications.data.slice(0, 4).map((item) => (
              <div className={`update-row ${!item.read_at ? 'unread' : ''}`} key={item.id}>
                <span className="update-dot" />
                <div>
                  <p>{item.text}</p>
                  <small>{dateLabel(item.created_at)}</small>
                  {item.status === 'needs_attention' && <Badge status="delivery needs attention" />}
                </div>
              </div>
            ))
          ) : (
            <Empty icon="spark" title="You're all caught up">
              Reminders and finished reports will appear here.
            </Empty>
          )}
        </section>
      </div>
      <section className="panel">
        <div className="section-heading">
          <div>
            <span className="eyebrow">QUIETLY WORKING IN THE BACKGROUND</span>
            <h3>Your assistant's status</h3>
          </div>
          <button className="text-button" onClick={() => navigate('features')}>
            Explore features
            <Icon name="chevron" size={12} />
          </button>
        </div>
        <p className="muted">
          {status?.runtime?.note || 'The assistant service is checking its background connections.'}
        </p>
        <div className="health-grid">
          {status?.runtime?.services?.length ? (
            status.runtime.services
              .filter((service) => service.id !== 'companion' || status.desktop_online)
              .map((service) => (
                <div className="health-item" key={service.id}>
                  <span
                    className={`health-dot ${['ready', 'working'].includes(service.status) ? 'good' : 'warm'}`}
                  />
                  <div>
                    <strong>{service.title}</strong>
                    <small>
                      {service.status === 'working'
                        ? 'Working on a saved task'
                        : service.status === 'ready'
                          ? 'Ready'
                          : service.status.replaceAll('_', ' ')}
                    </small>
                  </div>
                </div>
              ))
          ) : (
            <>
              <div className="health-item">
                <span className={`health-dot ${status?.scheduler_online ? 'good' : 'warm'}`} />
                <div>
                  <strong>Background schedules</strong>
                  <small>{status?.scheduler_online ? 'Ready' : 'Waiting for scheduler'}</small>
                </div>
              </div>
              <div className="health-item">
                <span className={`health-dot ${status?.desktop_online ? 'good' : 'warm'}`} />
                <div>
                  <strong>Laptop companion</strong>
                  <small>{status?.desktop_online ? 'Connected' : 'Offline · local jobs wait'}</small>
                </div>
              </div>
            </>
          )}
        </div>
        <small>Local routines need this laptop awake. Phone and cloud access are not connected yet.</small>
      </section>
    </div>
  );
}
