import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Api, errorMessage } from './api';
import type { Workflow, WorkflowDefinition } from './types';
import { ErrorNotice, Modal } from './ui';

const templates = [
  { id: 'notify', title: 'A gentle check-in', detail: 'A reminder in your updates and Telegram.' },
  { id: 'browser', title: 'Open a website', detail: 'Use the dedicated laptop browser.' },
  { id: 'note', title: 'Create a local note', detail: 'Write a new file in one approved folder.' },
  { id: 'research', title: 'Research and report', detail: 'Gather evidence and export a report.' },
];

export function WorkflowEditor({
  api,
  workflow,
  close,
  saved,
}: {
  api: Api;
  workflow?: Workflow;
  close: () => void;
  saved: () => void;
}) {
  const requestId = useRef(crypto.randomUUID());
  const [advanced, setAdvanced] = useState(!!workflow);
  const [template, setTemplate] = useState('notify');
  const [name, setName] = useState('');
  const [content, setContent] = useState('');
  const [folder, setFolder] = useState('');
  const [filename, setFilename] = useState('my-note.md');
  const [url, setUrl] = useState('https://www.youtube.com/');
  const [recurrence, setRecurrence] = useState('manual');
  const [time, setTime] = useState('09:00');
  const [definition, setDefinition] = useState(
    JSON.stringify(
      workflow
        ? Object.fromEntries(
            Object.entries(workflow).filter(([key]) =>
              [
                'name',
                'description',
                'steps',
                'allowed_tools',
                'allowed_domains',
                'allowed_paths',
                'trigger',
              ].includes(key),
            ),
          )
        : {
            name: 'My workflow',
            description: '',
            steps: [{ tool: 'notify', args: { message: 'Time for a quick check-in.' } }],
            allowed_tools: ['notify'],
            allowed_domains: [],
            allowed_paths: [],
            trigger: { kind: 'manual' },
          },
      null,
      2,
    ),
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function save(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      let data: WorkflowDefinition;
      if (advanced) data = JSON.parse(definition);
      else {
        data = {
          name,
          description: templates.find((item) => item.id === template)?.detail || '',
          steps: [],
          allowed_tools: [],
          allowed_domains: [],
          allowed_paths: [],
          trigger:
            recurrence === 'manual' ? { kind: 'manual' } : { kind: 'daily', time, timezone: 'Asia/Kolkata' },
        };
        if (template === 'notify') {
          data.allowed_tools = ['notify'];
          data.steps = [{ tool: 'notify', args: { message: content } }];
        }
        if (template === 'research') {
          data.allowed_tools = ['research.run'];
          data.steps = [
            {
              tool: 'research.run',
              args: { topic: content, include_academic: false, report_kind: 'standard' },
            },
          ];
        }
        if (template === 'browser') {
          const target = new URL(url);
          if (target.protocol !== 'https:' || target.username || target.password)
            throw new Error('Choose a public HTTPS website without credentials in its address.');
          data.allowed_domains = [target.hostname];
          data.allowed_tools = ['browser.run'];
          data.steps = [{ tool: 'browser.run', args: { actions: [{ type: 'navigate', url: target.href }] } }];
        }
        if (template === 'note') {
          if (!filename.trim() || /[<>:"/\\|?*]/.test(filename) || filename === '.' || filename === '..')
            throw new Error('Use a file name without folder separators or special characters.');
          const approved = folder.replace(/[\\/]+$/, '');
          data.allowed_paths = [approved];
          data.allowed_tools = ['file.write'];
          data.steps = [
            { tool: 'file.write', args: { path: approved + '\\' + filename, content, overwrite: false } },
          ];
        }
      }
      await api.request(workflow ? `/v1/workflows/${workflow.id}/` : '/v1/workflows/', {
        method: workflow ? 'PATCH' : 'POST',
        body: JSON.stringify({ ...data, ...(workflow ? {} : { request_id: requestId.current }) }),
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
    <Modal title={workflow ? 'Edit the reviewed workflow' : 'Give a routine a home'} close={close}>
      <p className="muted">
        {workflow
          ? 'Saving disables this workflow and cancels pending runs. Review the changed permissions before enabling it again.'
          : 'Start from a small template. This saves a draft; you review and enable it separately.'}
      </p>
      <div className="segmented">
        <button
          className={!advanced ? 'selected' : ''}
          disabled={!!workflow}
          onClick={() => setAdvanced(false)}
        >
          Simple setup
        </button>
        <button className={advanced ? 'selected' : ''} onClick={() => setAdvanced(true)}>
          Advanced definition
        </button>
      </div>
      <form className="stack" onSubmit={save}>
        {advanced ? (
          <label>
            Workflow definition
            <small>Browser steps support exact button names and field labels, bounded waits and scrolling. Every write needs the reviewed page URL and expected text.</small>
            <textarea
              className="code-editor"
              rows={17}
              required
              value={definition}
              onChange={(e) => setDefinition(e.target.value)}
            />
          </label>
        ) : (
          <>
            <div className="template-grid">
              {templates.map((item) => (
                <button
                  type="button"
                  className={`template-choice ${template === item.id ? 'selected' : ''}`}
                  key={item.id}
                  onClick={() => setTemplate(item.id)}
                >
                  <strong>{item.title}</strong>
                  <span>{item.detail}</span>
                </button>
              ))}
            </div>
            <label>
              Name
              <input
                required
                maxLength={160}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My morning check-in"
              />
            </label>
            {template === 'browser' ? (
              <label>
                Website address
                <input required type="url" value={url} onChange={(e) => setUrl(e.target.value)} />
              </label>
            ) : (
              <label>
                {template === 'research'
                  ? 'Research topic'
                  : template === 'note'
                    ? 'Note content'
                    : 'Message'}
                <textarea
                  required
                  rows={3}
                  maxLength={template === 'research' ? 2000 : 4000}
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                />
              </label>
            )}
            {template === 'note' && (
              <>
                <label>
                  Approved folder
                  <input
                    required
                    value={folder}
                    onChange={(e) => setFolder(e.target.value)}
                    placeholder="C:\Users\YourName\Documents\Derek notes"
                  />
                </label>
                <label>
                  New file name
                  <input required value={filename} onChange={(e) => setFilename(e.target.value)} />
                </label>
                <small>
                  Existing files are not overwritten. This grants access to the named folder for this
                  workflow.
                </small>
              </>
            )}
            <label>
              When
              <select value={recurrence} onChange={(e) => setRecurrence(e.target.value)}>
                <option value="manual">Only when I choose Run now</option>
                <option value="daily">Every day</option>
              </select>
            </label>
            {recurrence === 'daily' && (
              <label>
                Time · Asia/Kolkata
                <input required type="time" value={time} onChange={(e) => setTime(e.target.value)} />
              </label>
            )}
          </>
        )}
        <ErrorNotice message={error} />
        <button className="button primary" disabled={busy}>
          {busy ? 'Saving…' : 'Save draft for review'}
        </button>
      </form>
    </Modal>
  );
}
