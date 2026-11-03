import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { FormEvent } from 'react';
import { Api, errorMessage, safeHttpUrl } from './api';
import { readChat, saveChat, stateKey } from './chatState';
import type { ChatState } from './chatState';
import { Markdown } from './Markdown';
import { Images } from './Images';
import { OrbitStage } from './OrbitStage';
import type {
  ActionProposal,
  Artifact,
  Citation,
  CommandResult,
  Conversation,
  Identifier,
  Message,
  Turn,
} from './types';
import { ErrorNotice, Icon, Loading, useResource } from './ui';

function SendAnswer({ api, commandId }: { api: Api; commandId: string }) {
  const [state, setState] = useState<'idle' | 'sending' | 'sent'>('idle');
  const [error, setError] = useState('');
  async function send() {
    if (state !== 'idle') return;
    setState('sending'); setError('');
    try { await api.post('/v1/telegram/send/', { command_id: commandId }); setState('sent'); }
    catch (failure) { setError(errorMessage(failure)); setState('idle'); }
  }
  return <><button type="button" className="icon-button answer-copy" aria-label={state === 'sent' ? 'Sent to Telegram' : state === 'sending' ? 'Sending to Telegram' : 'Send answer to Telegram'} title={state === 'sent' ? 'Sent to Telegram' : 'Send to your Telegram chat'} disabled={state !== 'idle'} onClick={() => void send()}>{state === 'sent' ? <Icon name="check" size={16} /> : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m22 2-7 20-4-9-9-4Z M22 2 11 13" /></svg>}</button>{error && <small role="alert">{error}</small>}<span className="sr-only" role="status">{state === 'sent' ? 'Answer sent to Telegram' : ''}</span></>;
}

export function ProposalCard({
  api,
  initial,
  refresh,
  resolved,
}: {
  api: Api;
  initial: ActionProposal;
  refresh: number;
  resolved: (text: string) => void;
}) {
  const state = useResource<ActionProposal>(api, `/v1/action-proposals/${initial.id}/`, refresh);
  const proposal = state.data || initial;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const active = proposal.status === 'pending' && Date.parse(proposal.expires_at) > now;
  async function decide(action: 'confirm' | 'cancel') {
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<{ message: string; proposal: ActionProposal }>(
        `/v1/action-proposals/${proposal.id}/${action}/`,
        { revision: proposal.revision, payload_digest: proposal.payload_digest },
      );
      state.setData(result.proposal);
      resolved(result.message);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="proposal-card">
      <span className="eyebrow">YOUR CONFIRMATION</span>
      <strong>Review this exact change</strong>
      <p>{proposal.readback}</p>
      <small>
        {active
          ? `Expires in ${Math.max(0, Math.ceil((Date.parse(proposal.expires_at) - now) / 1000))} seconds`
          : proposal.status === 'pending'
            ? 'Confirmation expired. Ask again for a fresh proposal.'
            : proposal.status.replaceAll('_', ' ')}
      </small>
      <div className="actions">
        <button
          className="button primary small"
          disabled={busy || !active || !!state.error}
          onClick={() => decide('confirm')}
        >
          Confirm change
        </button>
        <button
          className="button secondary small"
          disabled={busy || !active}
          onClick={() => decide('cancel')}
        >
          Cancel
        </button>
      </div>
      <ErrorNotice message={error || state.error} />
    </div>
  );
}

function Citations({ citations }: { citations?: Citation[] }) {
  return citations?.length ? (
    <details className="sources">
      <summary>Sources ({citations.length})</summary>
      {citations.map((source, index) => {
        const href = safeHttpUrl(source.url);
        return href ? (
          <a href={href} key={`${href}-${index}`} target="_blank" rel="noopener noreferrer">
            <span>{index + 1}</span>
            {source.title || source.domain || new URL(href).hostname}
            <Icon name="link" size={12} />
          </a>
        ) : null;
      })}
    </details>
  ) : null;
}
function SearchSuggestions({ html }: { html?: string[] }) {
  return html?.length ? (
    <div className="search-suggestions">
      {html.map((content, index) => (
        <iframe
          key={index}
          title={`Google Search suggestions ${index + 1}`}
          srcDoc={content}
          sandbox="allow-popups"
          style={{ width: '100%', height: 100, border: 0 }}
        />
      ))}
    </div>
  ) : null;
}
function Artifacts({ artifacts, api }: { artifacts?: Artifact[]; api: Api }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function download(item: Artifact) {
    setBusy(true);
    setError(null);
    try {
      await api.download(
        `/v1/reports/${item.report_id || item.id}/download/?format=pdf`,
        `${item.title || item.name || 'report'}.pdf`,
      );
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return artifacts?.length ? (
    <div className="artifacts">
      {artifacts.map((item, index) =>
        item.report_id || item.id ? (
          <button
            className="button secondary small"
            disabled={busy}
            key={index}
            onClick={() => download(item)}
          >
            <Icon name="file" size={16} />
            {item.title || item.name || 'Download report'}
          </button>
        ) : null,
      )}
      <ErrorNotice message={error} />
    </div>
  ) : null;
}

const suggestions = [
  {
    icon: 'file' as const,
    title: 'Explore an idea',
    detail: 'Research a topic with sources',
    prompt: 'Research the latest developments in ',
  },
  {
    icon: 'clock' as const,
    title: 'Free up your day',
    detail: 'Set a reminder or recurring task',
    prompt: 'Remind me every weekday at 9 AM to ',
  },
  {
    icon: 'spark' as const,
    title: 'Find your rhythm',
    detail: 'Draft an everyday automation',
    prompt: 'Draft a workflow that ',
  },
];
const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const done = () => {
      signal.removeEventListener('abort', abort);
      resolve();
    };
    const timer = setTimeout(done, ms);
    const abort = () => {
      clearTimeout(timer);
      reject(new DOMException('Aborted', 'AbortError'));
    };
    signal.addEventListener('abort', abort, { once: true });
  });

export function Chat({
  api,
  refresh,
  changed,
  onAutomations,
  localVoice = false,
  toolsEnabled = true,
  audioEnabled = toolsEnabled,
  testingWorkspace = false,
  active = true,
  historyTarget,
  onNavigateChat,
}: {
  api: Api;
  refresh: number;
  changed: () => void;
  onAutomations: () => void;
  localVoice?: boolean;
  toolsEnabled?: boolean;
  audioEnabled?: boolean;
  testingWorkspace?: boolean;
  active?: boolean;
  historyTarget?: HTMLElement | null;
  onNavigateChat?: () => void;
}) {
  const key = stateKey(api.token, api.base);
  const stored = useRef<ChatState>(readChat(key));
  const conversations = useResource<Conversation[]>(api, '/v1/conversations/', refresh);
  const [conversation, setConversation] = useState<Identifier | null>(stored.current.pending ? stored.current.conversation : null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState('');
  const [audio, setAudio] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(stored.current.pending);
  const [phase, setPhase] = useState('');
  const [recording, setRecording] = useState(false);
  const [historySearch, setHistorySearch] = useState('');
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const recorderTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transcriptEnd = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const field = input.current;
    if (!field) return;
    const resize = () => {
      field.style.height = 'auto';
      field.style.height = `${Math.min(field.scrollHeight, 180)}px`;
      field.style.overflowY = field.scrollHeight > 180 ? 'auto' : 'hidden';
    };
    resize();
    // Observe available width, so wrapped lines also resize after layout changes.
    let lastWidth = field.clientWidth;
    const widthObserver = new ResizeObserver(() => {
      if (field.clientWidth !== lastWidth) { lastWidth = field.clientWidth; resize(); }
    });
    widthObserver.observe(field);
    return () => widthObserver.disconnect();
  }, [text, audio, messages.length, pending]);

  const fileInput = useRef<HTMLInputElement>(null);
  const operation = useRef<AbortController | null>(null);
  const loadSequence = useRef(0);
  const mounted = useRef(true);
  const activeRef = useRef(active);
  activeRef.current = active;
  useEffect(() => {
    if (!active && recorder.current?.state === 'recording') recorder.current.stop();
  }, [active]);

  const remember = useCallback(
    (value: ChatState) => {
      stored.current = value;
      saveChat(key, value);
      setPending(value.pending);
    },
    [key],
  );
  useEffect(() => {
    if (active && messages.length) transcriptEnd.current?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'nearest' });
  }, [messages, busy, active]);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      operation.current?.abort();
      ++loadSequence.current;
      if (recorderTimer.current) clearTimeout(recorderTimer.current);
      if (recorder.current?.state === 'recording') {
        recorder.current.onstop = null;
        recorder.current.stop();
      }
      stream.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const openConversation = useCallback(
    async (id: Identifier) => {
      const seq = ++loadSequence.current;
      setLoading(true);
      setError(null);
      try {
        const result = await api.request<Conversation>(`/v1/conversations/${id}/`);
        if (!mounted.current || seq !== loadSequence.current) return;
        setConversation(id);
        setMessages(result.messages || []);
        remember({ ...stored.current, conversation: String(id) });
      } catch (error) {
        if (mounted.current && seq === loadSequence.current) setError(errorMessage(error));
      } finally {
        if (mounted.current && seq === loadSequence.current) setLoading(false);
      }
    },
    [api, remember],
  );
  useEffect(() => {
    const requestedConversation = () => new URLSearchParams(window.location.hash.split('?')[1] || '').get('conversation');
    const requested = requestedConversation();
    const id = stored.current.pending ? stored.current.conversation : requested;
    if (id && /^[0-9a-f-]{36}$/i.test(id)) void openConversation(id);
    const followLink = () => {
      const next = requestedConversation();
      if (next && /^[0-9a-f-]{36}$/i.test(next) && !stored.current.pending) void openConversation(next);
    };
    window.addEventListener('hashchange', followLink);
    return () => window.removeEventListener('hashchange', followLink);
  }, [openConversation]);

  async function finished(result: Turn) {
    remember({ conversation: String(result.conversation_id), pending: null });
    setConversation(result.conversation_id);
    setText('');
    setAudio(null);
    changed();
    await openConversation(result.conversation_id);
  }
  async function awaitCommand(command: CommandResult, signal: AbortSignal) {
    const deadline = Date.now() + 30 * 60 * 1000;
    while (['queued', 'running'].includes(command.status)) {
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
      remember({
        conversation: command.conversation_id,
        pending: { id: command.request_id, commandId: command.command_id },
      });
      setConversation(command.conversation_id);
      setPhase(
        command.status === 'queued' ? 'Your request is saved · waiting for Derek' : 'Derek is working on it',
      );
      if (Date.now() >= deadline)
        throw new Error('This request is still saved. Use Retrieve reply or inspect Command history.');
      await sleep(testingWorkspace ? 2500 : 1500, signal);
      while (testingWorkspace && document.hidden) await sleep(1000, signal);
      command = await api.request<CommandResult>(`/v1/commands/${command.command_id}/`, { signal });
    }
    if (!signal.aborted) await finished(command.response);
  }
  async function recover() {
    const request = stored.current.pending;
    if (!request || busy) return;
    const controller = new AbortController();
    operation.current = controller;
    setBusy(true);
    setError(null);
    setPhase('Retrieving the saved result…');
    try {
      const command = await api.request<CommandResult>(`/v1/commands/by-request/${request.id}/`, {
        signal: controller.signal,
      });
      await awaitCommand(command, controller.signal);
    } catch (error) {
      if (!controller.signal.aborted && mounted.current) setError(errorMessage(error));
    } finally {
      if (mounted.current && operation.current === controller) {
        setBusy(false);
        setPhase('');
      }
    }
  }
  async function stop() {
    const request = stored.current.pending;
    if (!request) return;
    operation.current?.abort();
    const controller = new AbortController();
    operation.current = controller;
    setBusy(true);
    setError(null);
    setPhase('Stopping this response…');
    try {
      const result = await api.post<{ message: string; conversation_id?: string }>('/v1/commands/cancel/', {
        request_id: request.id,
      });
      if (!mounted.current) return;
      remember({ conversation: result.conversation_id || stored.current.conversation, pending: null });
      if (result.conversation_id) await openConversation(result.conversation_id);
      else setMessages((previous) => [...previous, { role: 'assistant', content: result.message }]);
      changed();
    } catch (error) {
      if (mounted.current) setError(errorMessage(error));
    } finally {
      if (mounted.current) {
        setBusy(false);
        setPhase('');
      }
    }
  }
  function newConversation() {
    if (pending || busy || recording) return;
    ++loadSequence.current;
    setLoading(false);
    setConversation(null);
    setMessages([]);
    setError(null);
    setText('');
    setAudio(null);
    remember({ conversation: null, pending: null });
    history.replaceState(null, '', '#chat');
    onNavigateChat?.();
    requestAnimationFrame(() => input.current?.focus());
  }
  async function removeConversation(id: Identifier) {
    if (!window.confirm('Delete this conversation and its messages?')) return;
    setError(null);
    setBusy(true);
    try {
      await api.delete(`/v1/conversations/${id}/`);
      if (conversation === id) {
        setMessages([]);
        setConversation(null);
        remember({ conversation: null, pending: null });
      }
      changed();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  async function send(event: FormEvent) {
    event.preventDefault();
    if (busy || pending || recording || (!text.trim() && !audio)) return;
    const requestId = crypto.randomUUID();
    remember({ conversation: conversation ? String(conversation) : null, pending: { id: requestId } });
    const controller = new AbortController();
    operation.current = controller;
    setBusy(true);
    setError(null);
    setPhase(audio ? 'Transcribing your voice note…' : 'Saving your request…');
    setMessages((previous) => [
      ...previous,
      { role: 'user', content: audio ? `Voice note · ${audio.name}` : text.trim() },
    ]);
    try {
      if (audio) {
        const body = new FormData();
        body.append('audio', audio);
        body.append('request_id', requestId);
        if (conversation) body.append('conversation_id', String(conversation));
        const result = await api.request<Turn>('/v1/turn', {
          method: 'POST',
          body,
          signal: controller.signal,
        });
        if (['queued', 'running'].includes(result.status || '')) {
          const command = await api.request<CommandResult>(`/v1/commands/by-request/${requestId}/`, {
            signal: controller.signal,
          });
          await awaitCommand(command, controller.signal);
        } else if (!controller.signal.aborted) await finished(result);
      } else {
        const command = await api.request<CommandResult>('/v1/commands/', {
          method: 'POST',
          body: JSON.stringify({
            text: text.trim(),
            request_id: requestId,
            ...(conversation ? { conversation_id: conversation } : {}),
          }),
          signal: controller.signal,
        });
        await awaitCommand(command, controller.signal);
      }
    } catch (error) {
      if (!controller.signal.aborted && mounted.current)
        setError(
          `${errorMessage(error)} Your request ID is kept. Retrieve its saved result or stop it before sending another.`,
        );
    } finally {
      if (mounted.current && operation.current === controller) {
        setBusy(false);
        setPhase('');
        input.current?.focus();
      }
    }
  }
  function selectAudio(file?: File) {
    if (!file) return;
    if (file.size > 20 * 1024 * 1024) {
      setError('Choose an audio file smaller than 20 MB.');
      return;
    }
    setError(null);
    setAudio(file);
    setText('');
  }
  async function toggleRecording() {
    if (recording) {
      recorder.current?.stop();
      return;
    }
    setError(null);
    if (!navigator.mediaDevices || typeof MediaRecorder === 'undefined') {
      setError('Microphone recording needs HTTPS or localhost. You can upload an audio file instead.');
      return;
    }
    try {
      const source = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current || !activeRef.current) {
        source.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = source;
      const mime = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4'].find((type) =>
        MediaRecorder.isTypeSupported(type),
      );
      const instance = new MediaRecorder(source, mime ? { mimeType: mime } : undefined);
      recorder.current = instance;
      const chunks: BlobPart[] = [];
      let size = 0;
      instance.ondataavailable = (event) => {
        if (event.data.size) {
          chunks.push(event.data);
          size += event.data.size;
          if (size > 20 * 1024 * 1024 && instance.state === 'recording') instance.stop();
        }
      };
      instance.onstop = () => {
        if (recorderTimer.current) clearTimeout(recorderTimer.current);
        source.getTracks().forEach((track) => track.stop());
        if (!mounted.current) return;
        const ext = instance.mimeType.includes('mp4')
          ? 'm4a'
          : instance.mimeType.includes('ogg')
            ? 'ogg'
            : 'webm';
        selectAudio(new File(chunks, `voice-note.${ext}`, { type: instance.mimeType }));
        setRecording(false);
      };
      instance.onerror = () => {
        setError('Recording stopped unexpectedly. Please try again.');
        source.getTracks().forEach((track) => track.stop());
        setRecording(false);
      };
      instance.start(1000);
      setRecording(true);
      recorderTimer.current = setTimeout(() => {
        if (instance.state === 'recording') instance.stop();
      }, 120_000);
    } catch (error) {
      setError(errorMessage(error));
      stream.current?.getTracks().forEach((track) => track.stop());
    }
  }
  async function openVoice() {
    setError(null);
    try {
      await api.post('/v1/local/voice/', { mode: 'online' });
    } catch (error) {
      setError(errorMessage(error));
    }
  }
  const [imagesOpen, setImagesOpen] = useState(false);
  const [copiedReply, setCopiedReply] = useState<number | null>(null);
  async function copyReply(text: string, index: number) {
    try { await navigator.clipboard.writeText(text); setCopiedReply(index); }
    catch { setError('Could not copy. Select the answer text to copy it.'); }
  }
  const blocked = busy || !!pending || recording || loading;
  return (
    <div className="chat-layout">
      <section className="chat-main" aria-label="Conversation">
        <div className={`transcript ${messages.length ? '' : 'transcript-welcome'}`} aria-live="polite">
          {loading ? (
            <Loading />
          ) : messages.length ? (
            messages.map((message, index) => (
              <article
                key={message.id || index}
                aria-label={message.role === 'user' ? 'Your message' : 'Derek response'}
                className={`message ${message.role === 'user' ? 'from-user' : 'from-assistant'}`}
              >
                {message.role === 'assistant' ? (
                  <><Markdown text={message.content} /><div className="reply-actions"><button className="icon-button answer-copy" aria-label={copiedReply === index ? 'Answer copied' : 'Copy answer'} title={copiedReply === index ? 'Copied' : 'Copy answer'} onClick={() => void copyReply(message.content, index)}>{copiedReply === index ? <Icon name="check" size={16} /> : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="8" y="8" width="12" height="13" rx="2" /><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3" /></svg>}</button>{testingWorkspace && message.command_id && message.status === 'completed' && !message.action_proposals?.length && <SendAnswer api={api} commandId={message.command_id} />}</div></>
                ) : (
                  <p className="message-content">{message.content}</p>
                )}
                <Citations citations={message.citations} />
                <SearchSuggestions html={message.search_suggestions_html} />
                <Artifacts artifacts={message.artifacts} api={api} />
                {message.action_proposals?.map((proposal) => (
                  <ProposalCard
                    key={proposal.id}
                    api={api}
                    initial={proposal}
                    refresh={refresh}
                    resolved={() => {
                      if (conversation) void openConversation(conversation);
                      changed();
                    }}
                  />
                ))}
                {message.job_id && (
                  <a className="inline-action" href="#reports">
                    Research queued · View reports
                    <Icon name="arrow" size={14} />
                  </a>
                )}
                {Boolean(message.approval_needed) && (
                  <button className="inline-action" onClick={onAutomations}>
                    Your review is needed · Open approvals
                  </button>
                )}
                {message.handled_by === 'built_in' && (
                  <small className="quick-reply-note">Quick local reply · no model call</small>
                )}
              </article>
            ))
          ) : (
            <div className="welcome">
              {active && <OrbitStage />}
              {toolsEnabled && <div className="suggestions">
                {suggestions.map((item) => (
                  <button
                    key={item.title}
                    disabled={!!pending}
                    onClick={() => {
                      setText(item.prompt);
                      input.current?.focus();
                    }}
                  >
                    <Icon name={item.icon} size={21} />
                    <strong>{item.title}</strong>
                    <span>{item.detail}</span>
                    <Icon name="arrow" size={16} />
                  </button>
                ))}
              </div>}
            </div>
          )}
          {busy && (
            <div className="thinking" role="status">
              <span />
              <span />
              <span />
              {phase}
            </div>
          )}
          <div ref={transcriptEnd} />
        </div>
        {testingWorkspace && <><button type="button" className="button secondary image-chat-toggle" aria-expanded={imagesOpen} onClick={() => setImagesOpen(value => !value)}>{imagesOpen ? 'Close image generation' : 'Generate image'}</button>{(imagesOpen || conversation) && <Images api={api} refresh={refresh} changed={changed} conversationId={conversation ? String(conversation) : undefined} compact showForm={imagesOpen} onCreated={job => {
          setImagesOpen(false);
          if (job.conversation_id) {
            setConversation(job.conversation_id);
            remember({ ...stored.current, conversation: job.conversation_id });
            history.replaceState(null, '', `#chat?conversation=${encodeURIComponent(job.conversation_id)}`);
          }
        }} />}</>}
        <div className={`composer-area ${messages.length || pending ? 'composer-in-session' : ''}`}>
          <ErrorNotice message={error} />
          {pending && (
            <div className="notice recovery-bar">
              <div>
                <strong>{busy ? 'Your request is saved' : 'Pick up your unfinished request'}</strong>
                <p>You can leave and come back. Retrieving never sends the command again.</p>
              </div>
              <div className="actions">
                <button className="button secondary small" disabled={busy} onClick={recover}>
                  Retrieve reply
                </button>
                <button className="text-button" onClick={stop}>
                  Stop response
                </button>
                <a className="text-button" href="#commands">
                  Command history
                </a>
              </div>
            </div>
          )}
          <form className={`composer ${recording ? 'recording' : ''}`} onSubmit={send}>
            {audio ? (
              <div className="audio-preview">
                <Icon name="mic" />
                <span>
                  {audio.name}
                  <small>Ready to send · {(audio.size / 1024).toFixed(0)} KB</small>
                </span>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Remove audio"
                  onClick={() => setAudio(null)}
                  disabled={blocked}
                >
                  <Icon name="close" size={16} />
                </button>
              </div>
            ) : (
              <textarea
                ref={input}
                aria-label="Message your assistant"
                value={text}
                maxLength={12000}
                onChange={(event) => setText(event.target.value)}
                placeholder={
                  recording
                    ? 'Recording… click the microphone to finish.'
                    : 'Ask anything, plan something, or get things done…'
                }
                disabled={blocked}
                rows={1}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    if (!blocked && text.trim()) event.currentTarget.form?.requestSubmit();
                  }
                }}
              />
            )}
            <div className="composer-bottom">
              <div className="composer-tools">
                {audioEnabled && <>
                {localVoice && (
                  <button type="button" className="text-button" onClick={openVoice} disabled={blocked}>
                    Voice window
                  </button>
                )}
                <button
                  type="button"
                  className={`icon-button ${recording ? 'is-recording' : ''}`}
                  aria-label={recording ? 'Stop recording' : 'Record a voice note'}
                  disabled={busy || !!pending || loading}
                  onClick={toggleRecording}
                >
                  <Icon name="mic" size={20} />
                </button>
                <button
                  type="button"
                  className="text-button audio-upload"
                  aria-label="Upload audio"
                  title="Upload audio"
                  disabled={blocked}
                  onClick={() => fileInput.current?.click()}
                >
                  <Icon name="plus" size={18} /><span className="audio-upload-label">Upload audio</span>
                </button>
                <input
                  ref={fileInput}
                  type="file"
                  accept="audio/*,.webm,.m4a,.wav,.mp3,.ogg"
                  hidden
                  onChange={(event) => {
                    selectAudio(event.target.files?.[0]);
                    event.target.value = '';
                  }}
                />
                </>}
              </div>
              <button
                type="submit"
                className="send-button"
                aria-label="Send message"
                disabled={blocked || (!text.trim() && !audio)}
              >
                <Icon name="arrow" size={20} />
              </button>
            </div>
          </form>
          <p className="composer-note">
            {recording
              ? 'Recording up to 2 minutes. Review before sending.'
              : 'Enter to send · Shift + Enter for a new line · Important changes need your confirmation'}
          </p>
        </div>
      </section>
      {historyTarget && createPortal(<section className="chat-history" aria-label="Conversation history">
        <div className="section-heading">
          <h2>Conversations</h2>
          <button
            className="icon-button"
            aria-label="New chat"
            disabled={busy || !!pending || recording}
            onClick={newConversation}
          >
            <Icon name="plus" size={18} />
            <span>New chat</span>
          </button>
        </div>
        <input
          type="search"
          className="history-search"
          aria-label="Search conversations"
          placeholder="Find a conversation…"
          value={historySearch}
          onChange={(e) => setHistorySearch(e.target.value)}
        />
        <ErrorNotice message={conversations.error} />
        {conversations.loading && !conversations.data ? (
          <Loading />
        ) : conversations.data?.length ? (
          <div className="history-list">
            {conversations.data
              .filter((item) => item.title.toLowerCase().includes(historySearch.toLowerCase()))
              .map((item) => (
                <div key={item.id} className={`history-item ${conversation === item.id ? 'current' : ''}`}>
                  <button
                    className="history-open"
                    disabled={busy || !!pending || recording}
                    onClick={() => {
                      history.replaceState(null, '', `#chat?conversation=${encodeURIComponent(item.id)}`);
                      onNavigateChat?.();
                      void openConversation(item.id);
                    }}
                  >
                    <span>{item.title || 'Untitled conversation'}</span>
                  </button>
                  <button
                    className="icon-button history-delete"
                    aria-label={`Delete ${item.title || 'conversation'}`}
                    disabled={busy || !!pending || recording}
                    onClick={() => removeConversation(item.id)}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6" /></svg>
                  </button>
                </div>
              ))}
          </div>
        ) : (
          <p className="muted quiet">Your conversations will find a home here.</p>
        )}
      </section>, historyTarget)}
    </div>
  );
}
