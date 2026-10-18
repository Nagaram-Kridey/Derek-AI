import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Api, errorMessage } from './api';
import type { Schedule, ScheduledTask } from './types';
import { ErrorNotice, Modal } from './ui';
import { localDateInput, scheduleLabel } from './schedules';

export function TaskEditor({
  api,
  task,
  close,
  saved,
}: {
  api: Api;
  task?: ScheduledTask;
  close: () => void;
  saved: () => void;
}) {
  const requestId = useRef(crypto.randomUUID());
  const [kind, setKind] = useState(task?.kind || 'reminder');
  const [name, setName] = useState(task?.name || '');
  const [content, setContent] = useState(task?.payload.message || task?.payload.topic || '');
  const [recurrence, setRecurrence] = useState<Schedule['kind']>(task?.schedule.kind || 'once');
  const [at, setAt] = useState(localDateInput(task?.schedule.at));
  const [time, setTime] = useState(task?.schedule.time || '09:00');
  const [days, setDays] = useState(task?.schedule.weekdays || [0, 1, 2, 3, 4]);
  const [format, setFormat] = useState(task?.payload.report_kind || 'standard');
  const [academic, setAcademic] = useState(task?.payload.include_academic || false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const schedule: Schedule =
    recurrence === 'once'
      ? { kind: 'once', at: at ? `${at}:00+05:30` : undefined, timezone: 'Asia/Kolkata' }
      : {
          kind: recurrence,
          time,
          timezone: 'Asia/Kolkata',
          ...(recurrence === 'weekly' ? { weekdays: days } : {}),
        };
  async function save(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (recurrence === 'weekly' && !days.length) {
      setError('Choose at least one day.');
      return;
    }
    if (recurrence === 'once' && (!schedule.at || Date.parse(schedule.at) <= Date.now())) {
      setError('Choose a future date and time in Asia/Kolkata.');
      return;
    }
    setBusy(true);
    const payload =
      kind === 'reminder'
        ? { message: content }
        : { topic: content, report_kind: format, include_academic: academic };
    try {
      await api.request(task ? `/v1/tasks/${task.id}/` : '/v1/tasks/', {
        method: task ? 'PATCH' : 'POST',
        body: JSON.stringify({
          name,
          ...(task ? { expected: task.revision } : { kind, request_id: requestId.current }),
          payload,
          schedule,
        }),
      });
      saved();
      close();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={task ? 'Edit your routine' : 'Make room for a routine'} close={close}>
      <form onSubmit={save} className="stack">
        <label>
          Name
          <input
            required
            maxLength={160}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="An afternoon break"
          />
        </label>
        {!task && (
          <label>
            Task type
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="reminder">Reminder</option>
              <option value="research">Research report</option>
            </select>
          </label>
        )}
        <label>
          {kind === 'reminder' ? 'What should Derek remind you?' : 'Research topic'}
          <textarea
            required
            maxLength={kind === 'research' ? 2000 : 4000}
            minLength={kind === 'research' ? 3 : 1}
            rows={3}
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
        </label>
        {kind === 'research' && (
          <>
            <label>
              Report format
              <select value={format} onChange={(e) => setFormat(e.target.value)}>
                <option value="standard">Research report</option>
                <option value="project_ideas">Five project ideas and a top-two shortlist</option>
              </select>
            </label>
            <label className="checkbox-label">
              <input type="checkbox" checked={academic} onChange={(e) => setAcademic(e.target.checked)} />
              Include academic sources
            </label>
          </>
        )}
        <label>
          Repeat
          <select value={recurrence} onChange={(e) => setRecurrence(e.target.value as Schedule['kind'])}>
            <option value="once">One time</option>
            <option value="daily">Every day</option>
            <option value="weekly">Selected days each week</option>
          </select>
        </label>
        {recurrence === 'once' ? (
          <label>
            Date and time · Asia/Kolkata
            <input required type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />
          </label>
        ) : (
          <label>
            Time · Asia/Kolkata
            <input required type="time" value={time} onChange={(e) => setTime(e.target.value)} />
          </label>
        )}
        {recurrence === 'weekly' && (
          <div>
            <span className="field-label">Days</span>
            <div className="weekday-picker">
              {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, index) => (
                <button
                  type="button"
                  key={day}
                  className={days.includes(index) ? 'selected' : ''}
                  aria-pressed={days.includes(index)}
                  onClick={() =>
                    setDays((previous) =>
                      previous.includes(index)
                        ? previous.filter((value) => value !== index)
                        : [...previous, index].sort(),
                    )
                  }
                >
                  {day}
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="schedule-preview">
          <strong>Review before saving</strong>
          <p>
            {name || 'Your routine'} · {scheduleLabel(schedule)}
          </p>
          <p>
            {task?.enabled === false
              ? 'This routine stays paused after saving.'
              : 'This routine becomes active when saved.'}{' '}
            Local schedules need the laptop awake.
          </p>
        </div>
        <ErrorNotice message={error} />
        <div className="actions">
          <button className="button primary" disabled={busy}>
            {busy ? 'Saving…' : task ? 'Save changes' : 'Create routine'}
          </button>
          <button type="button" className="button secondary" disabled={busy} onClick={close}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}
