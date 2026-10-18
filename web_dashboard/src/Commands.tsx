import { useState } from 'react';
import { Api, errorMessage } from './api';
import { ProposalCard } from './Chat';
import { Markdown } from './Markdown';
import type { CommandResult } from './types';
import { Badge, Empty, ErrorNotice, Icon, Loading, dateLabel, useResource } from './ui';

function CommandDetail({
  api,
  id,
  refresh,
  changed,
}: {
  api: Api;
  id: string;
  refresh: number;
  changed: () => void;
}) {
  const result = useResource<CommandResult>(api, `/v1/commands/${id}/`, refresh);
  const events = useResource<{
    events: { id: number; kind: string; created_at: string; detail: { message?: string } }[];
  }>(api, `/v1/commands/${id}/events/`, refresh);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const command = result.data;
  async function stop() {
    if (!command) return;
    setBusy(true);
    setError(null);
    try {
      await api.post('/v1/commands/cancel/', { request_id: command.request_id });
      changed();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel command-detail">
      <ErrorNotice message={error || result.error} />
      {result.loading && !command ? (
        <Loading />
      ) : (
        command && (
          <>
            <div className="section-heading">
              <Badge status={command.status} />
              <small>
                {command.channel} · {dateLabel(command.created_at)}
              </small>
            </div>
            <h3>Your request</h3>
            <p className="request-text">{command.input_text}</p>
            {command.started_at && (
              <p className="muted detail-time">
                Started {dateLabel(command.started_at)}
                {command.finished_at ? ` · Finished ${dateLabel(command.finished_at)}` : ''}
              </p>
            )}
            {['queued', 'running'].includes(command.status) && (
              <div className="notice">
                <p>
                  {command.status === 'queued'
                    ? 'Your command is saved and waiting for the conversation worker.'
                    : 'The assistant is processing this command.'}{' '}
                  You can leave this page; the saved work remains available.
                </p>
                {command.channel === 'web' && (
                  <button className="button secondary small" disabled={busy} onClick={stop}>
                    Stop this response
                  </button>
                )}
              </div>
            )}
            {command.status === 'needs_attention' && (
              <div className="notice warning">
                An outcome is uncertain. Inspect the saved actions and any connected service before requesting
                the same change again.
              </div>
            )}
            {command.error && <p className="error-text">{command.error}</p>}
            {command.response?.reply_text && (
              <div className="saved-answer">
                <span className="eyebrow">SAVED REPLY</span>
                <Markdown text={command.response.reply_text} />
              </div>
            )}
            {command.proposals?.map((proposal) => (
              <ProposalCard
                api={api}
                key={proposal.id}
                initial={proposal}
                refresh={refresh}
                resolved={() => changed()}
              />
            ))}
            {!!command.actions?.length && (
              <div className="action-history">
                <h3>Saved actions</h3>
                {command.actions.map((action) => (
                  <div className="list-row" key={action.id}>
                    <div>
                      <strong>{action.tool.replaceAll('_', ' ')}</strong>
                      {action.result.message && <p>{action.result.message}</p>}
                    </div>
                    <Badge status={action.status} />
                  </div>
                ))}
              </div>
            )}
            <a className="button secondary small" href={`#chat?conversation=${command.conversation_id}`}>
              Open conversation
              <Icon name="arrow" size={14} />
            </a>
            <details className="command-timeline">
              <summary>Command timeline</summary>
              <ol>
                {events.data?.events.map((event) => (
                  <li key={event.id}>
                    <strong>{event.kind.replaceAll('_', ' ')}</strong>
                    <time>{dateLabel(event.created_at)}</time>
                  </li>
                ))}
              </ol>
            </details>
          </>
        )
      )}
    </section>
  );
}

export function Commands({ api, refresh, changed }: { api: Api; refresh: number; changed: () => void }) {
  const commands = useResource<CommandResult[]>(api, '/v1/commands/', refresh);
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const visible =
    commands.data?.filter(
      (command) =>
        (filter === 'all' ||
          (filter === 'active'
            ? ['queued', 'running', 'awaiting_confirmation'].includes(command.status)
            : ['failed', 'needs_attention'].includes(command.status))) &&
        command.input_text.toLowerCase().includes(search.toLowerCase()),
    ) || [];
  const id = selected || visible[0]?.command_id;
  return (
    <div className="stack">
      <div className="section-heading">
        <div>
          <h2>Nothing gets lost</h2>
          <p className="muted">Saved requests, exact confirmations, and the outcome of each action.</p>
        </div>
        <button className="button secondary small" onClick={changed}>
          <Icon name="refresh" size={15} />
          Refresh
        </button>
      </div>
      <ErrorNotice message={commands.error} />
      <div className="filter-bar">
        <input
          type="search"
          aria-label="Search commands"
          placeholder="Find a request…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          value={filter}
          aria-label="Filter commands"
          onChange={(e) => {
            setFilter(e.target.value);
            setSelected(null);
          }}
        >
          <option value="all">All requests</option>
          <option value="active">In progress / review</option>
          <option value="attention">Needs attention</option>
        </select>
      </div>
      {commands.loading && !commands.data ? (
        <Loading />
      ) : visible.length ? (
        <div className="command-layout">
          <div className="command-list">
            {visible.map((command) => (
              <button
                className={`command-row ${command.command_id === id ? 'selected' : ''}`}
                key={command.command_id}
                onClick={() => setSelected(command.command_id)}
              >
                <span>{command.input_text}</span>
                <div>
                  <Badge status={command.status} />
                  <small>{dateLabel(command.created_at)}</small>
                </div>
              </button>
            ))}
          </div>
          {id && <CommandDetail key={id} api={api} id={id} refresh={refresh} changed={changed} />}
        </div>
      ) : (
        <Empty icon="chat" title="A clear view of every request">
          {search || filter !== 'all'
            ? 'No requests match this view.'
            : 'Your conversations will appear here as you use Derek.'}
        </Empty>
      )}
    </div>
  );
}
