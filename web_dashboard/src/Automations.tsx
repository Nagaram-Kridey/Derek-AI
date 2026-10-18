import { useState } from 'react';
import { Api, errorMessage } from './api';
import type { Approval, ScheduledTask, Workflow, Run } from './types';
import { Badge, Empty, ErrorNotice, Icon, JsonDetails, Loading, Modal, dateLabel, useResource } from './ui';
import { TaskEditor } from './TaskEditor';
import { WorkflowEditor } from './WorkflowEditor';
import { scheduleLabel } from './schedules';

function TaskHistory({ api, task, close }: { api: Api; task: ScheduledTask; close: () => void }) {
  const history = useResource<{ id: string; scheduled_for: string; status: string; error: string }[]>(
    api,
    `/v1/tasks/${task.id}/history/`,
  );
  return (
    <Modal title={`${task.name} · recent runs`} close={close}>
      <p className="muted">
        A scheduled occurrence is saved before dispatch. Interrupted or uncertain work is kept for review.
      </p>
      <ErrorNotice message={history.error} />
      {history.loading ? (
        <Loading />
      ) : history.data?.length ? (
        history.data.map((item) => (
          <div className="list-row" key={item.id}>
            <div>
              <strong>{dateLabel(item.scheduled_for)}</strong>
              {item.error && <p className="error-text">{item.error}</p>}
            </div>
            <Badge status={item.status} />
          </div>
        ))
      ) : (
        <Empty icon="clock" title="Waiting for the first run">
          This routine has no saved occurrences yet.
        </Empty>
      )}
    </Modal>
  );
}

function ReviewWorkflow({
  workflow,
  close,
  enable,
  busy,
}: {
  workflow: Workflow;
  close: () => void;
  enable: () => void;
  busy: boolean;
}) {
  return (
    <Modal title="Review this workflow" close={close}>
      <div className="stack">
        <div>
          <h3>{workflow.name}</h3>
          <p>{workflow.description}</p>
        </div>
        <div className="schedule-preview">
          <strong>Trigger</strong>
          <p>
            {workflow.trigger.kind === 'manual'
              ? 'Only when you choose Run now'
              : scheduleLabel(workflow.trigger as ScheduledTask['schedule'])}
          </p>
        </div>
        <div className="scope">
          <strong>Allowed actions</strong>
          <p>{workflow.allowed_tools.join(', ')}</p>
          <strong>Allowed websites</strong>
          <p>{workflow.allowed_domains.join(', ') || 'None'}</p>
          <strong>Allowed folders</strong>
          <p>{workflow.allowed_paths.join(', ') || 'None'}</p>
        </div>
        <ol className="workflow-steps">
          {workflow.steps.map((step, index) => (
            <li key={index}>
              <strong>{step.tool.replaceAll('.', ' · ')}</strong>
              <JsonDetails value={step.args} label="Exact action details" />
            </li>
          ))}
        </ol>
        <p className="muted">
          Enabling allows these reviewed steps to run on this trigger. Purchases, payments, security changes
          and permanent deletion still pause for separate approval. Laptop actions wait while your companion
          is offline.
        </p>
        <div className="actions">
          <button className="button primary" disabled={busy} onClick={enable}>
            Enable this reviewed workflow
          </button>
          <button className="button secondary" disabled={busy} onClick={close}>
            Keep as draft
          </button>
        </div>
      </div>
    </Modal>
  );
}

export function Automations({ api, refresh, changed }: { api: Api; refresh: number; changed: () => void }) {
  const tasks = useResource<ScheduledTask[]>(api, '/v1/tasks/', refresh);
  const workflows = useResource<Workflow[]>(api, '/v1/workflows/', refresh);
  const approvals = useResource<Approval[]>(api, '/v1/approvals/', refresh);
  const runs = useResource<Run[]>(api, '/v1/runs/', refresh);
  const [taskEditor, setTaskEditor] = useState<ScheduledTask | 'new' | null>(null);
  const [workflowEditor, setWorkflowEditor] = useState<Workflow | 'new' | null>(null);
  const [review, setReview] = useState<Workflow | null>(null);
  const [history, setHistory] = useState<ScheduledTask | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  async function act(path: string, method = 'POST') {
    setBusy(true);
    setError(null);
    try {
      if (method === 'DELETE') await api.delete(path);
      else await api.post(path);
      changed();
      return true;
    } catch (error) {
      setError(errorMessage(error));
      return false;
    } finally {
      setBusy(false);
    }
  }
  const visibleTasks =
    tasks.data?.filter(
      (task) => task.kind !== 'workflow' && task.name.toLowerCase().includes(search.toLowerCase()),
    ) || [];
  const visibleWorkflows =
    workflows.data?.filter((workflow) =>
      `${workflow.name} ${workflow.description}`.toLowerCase().includes(search.toLowerCase()),
    ) || [];
  return (
    <div className="stack">
      <div className="section-heading">
        <div>
          <h2>Your routines</h2>
          <p className="muted">Small reminders and reviewed workflows that make room in your day.</p>
        </div>
        <div className="actions">
          <button className="button secondary" onClick={() => setWorkflowEditor('new')}>
            <Icon name="plus" size={16} />
            Draft workflow
          </button>
          <button className="button primary" onClick={() => setTaskEditor('new')}>
            <Icon name="plus" size={16} />
            New routine
          </button>
        </div>
      </div>
      <ErrorNotice message={error || tasks.error || workflows.error || approvals.error || runs.error} />
      {!!approvals.data?.length && (
        <section className="panel">
          <h3>Your approval is needed</h3>
          {approvals.data.map((item) => (
            <article className="card" key={item.id}>
              <Badge status="needs approval" />
              <h3>{item.reason || item.action}</h3>
              <JsonDetails value={item.payload || item.details} label="Review the exact action" />
              <div className="actions">
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() => {
                    if (
                      window.confirm(
                        'Approve this exact sensitive action? Review its details before continuing.',
                      )
                    )
                      void act(`/v1/approvals/${item.id}/approve/`);
                  }}
                >
                  Approve once
                </button>
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() => act(`/v1/approvals/${item.id}/reject/`)}
                >
                  Reject
                </button>
              </div>
            </article>
          ))}
        </section>
      )}
      <input
        type="search"
        aria-label="Search routines"
        placeholder="Find a routine or workflow…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <section>
        <div className="section-heading">
          <h3>Reminders and research</h3>
          <small>
            {visibleTasks.length} routine{visibleTasks.length === 1 ? '' : 's'}
          </small>
        </div>
        {tasks.loading && !tasks.data ? (
          <Loading />
        ) : visibleTasks.length ? (
          <div className="card-grid">
            {visibleTasks.map((task) => (
              <article className="card" key={task.id}>
                <div className="section-heading">
                  <Badge
                    status={
                      task.enabled
                        ? 'scheduled'
                        : task.schedule.kind === 'once' && !task.next_run_at
                          ? 'inactive'
                          : 'paused'
                    }
                  />
                  <Icon name={task.kind === 'research' ? 'file' : 'clock'} size={18} />
                </div>
                <h3>{task.name}</h3>
                <p className="routine-content">{task.payload.message || task.payload.topic}</p>
                <p className="schedule-line">{scheduleLabel(task.schedule)}</p>
                <p className="muted">
                  {task.enabled ? `Next: ${dateLabel(task.next_run_at)}` : 'No new runs while inactive.'}
                </p>
                <div className="actions">
                  <button
                    className="button secondary small"
                    disabled={busy}
                    onClick={() => setTaskEditor(task)}
                  >
                    Edit
                  </button>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => act(`/v1/tasks/${task.id}/${task.enabled ? 'pause' : 'resume'}/`)}
                  >
                    {task.enabled ? 'Pause' : 'Resume'}
                  </button>
                  <button className="text-button" onClick={() => setHistory(task)}>
                    History
                  </button>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => {
                      if (window.confirm('Permanently delete this task and its occurrence history?'))
                        void act(`/v1/tasks/${task.id}/`, 'DELETE');
                    }}
                  >
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <Empty icon="clock" title={search ? 'No matching routines' : 'Room for a routine'}>
            Add a reminder or schedule regular research.
          </Empty>
        )}
      </section>
      <section>
        <div className="section-heading">
          <h3>Reviewed workflows</h3>
          <small>Each workflow has its own permissions</small>
        </div>
        {workflows.loading && !workflows.data ? (
          <Loading />
        ) : visibleWorkflows.length ? (
          <div className="card-grid">
            {visibleWorkflows.map((workflow) => (
              <article className="card" key={workflow.id}>
                <div className="section-heading">
                  <Badge status={workflow.enabled ? 'enabled' : 'draft / paused'} />
                  <Icon name="spark" size={18} />
                </div>
                <h3>{workflow.name}</h3>
                <p className="routine-content">{workflow.description}</p>
                <p className="schedule-line">
                  {workflow.trigger.kind === 'manual'
                    ? 'Run when you choose'
                    : scheduleLabel(workflow.trigger as ScheduledTask['schedule'])}
                </p>
                <div className="scope">
                  <strong>Permissions</strong>
                  <p>{workflow.allowed_tools.join(', ')}</p>
                  <p>Sites: {workflow.allowed_domains.join(', ') || 'None'}</p>
                  <p>Folders: {workflow.allowed_paths.join(', ') || 'None'}</p>
                </div>
                <div className="actions">
                  <button
                    className="button secondary small"
                    disabled={busy}
                    onClick={() =>
                      workflow.enabled ? act(`/v1/workflows/${workflow.id}/pause/`) : setReview(workflow)
                    }
                  >
                    {workflow.enabled ? 'Pause' : 'Review & enable'}
                  </button>
                  <button
                    className="button primary small"
                    disabled={busy || !workflow.enabled}
                    onClick={() => act(`/v1/workflows/${workflow.id}/run/`)}
                  >
                    <Icon name="play" size={13} />
                    Run now
                  </button>
                  <button className="text-button" disabled={busy} onClick={() => setWorkflowEditor(workflow)}>
                    Edit
                  </button>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => {
                      if (window.confirm('Delete this workflow and cancel pending runs?'))
                        void act(`/v1/workflows/${workflow.id}/`, 'DELETE');
                    }}
                  >
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <Empty title={search ? 'No matching workflows' : 'Give a routine a home'}>
            Choose a small template or describe an automation in chat.
          </Empty>
        )}
      </section>
      <section className="panel">
        <h3>Recent workflow runs</h3>
        {runs.data?.length ? (
          runs.data.map((run) => (
            <div className="list-row" key={run.id}>
              <div>
                <strong>{run.workflow_name || 'Workflow run'}</strong>
                <p className="muted">{dateLabel(run.created_at)}</p>
                {run.error && <p className="error-text">{run.error}</p>}
                <JsonDetails value={run.result} label="Saved results" />
              </div>
              <div className="actions">
                <Badge status={run.status} />
                {!['completed', 'failed', 'cancelled'].includes(run.status) && (
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => act(`/v1/runs/${run.id}/cancel/`)}
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>
          ))
        ) : (
          <p className="muted">Workflow results will appear here.</p>
        )}
      </section>
      {taskEditor && (
        <TaskEditor
          api={api}
          task={taskEditor === 'new' ? undefined : taskEditor}
          close={() => setTaskEditor(null)}
          saved={changed}
        />
      )}
      {workflowEditor && (
        <WorkflowEditor
          api={api}
          workflow={workflowEditor === 'new' ? undefined : workflowEditor}
          close={() => setWorkflowEditor(null)}
          saved={changed}
        />
      )}
      {history && <TaskHistory api={api} task={history} close={() => setHistory(null)} />}
      {review && (
        <ReviewWorkflow
          workflow={review}
          close={() => setReview(null)}
          busy={busy}
          enable={async () => {
            if (await act(`/v1/workflows/${review.id}/enable/`)) setReview(null);
          }}
        />
      )}
    </div>
  );
}
