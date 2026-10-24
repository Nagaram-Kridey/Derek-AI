export type Identifier = string | number;
export type Citation = { title?: string; url?: string; domain?: string; verified?: boolean };
export type Artifact = {
  id?: Identifier;
  report_id?: Identifier;
  title?: string;
  name?: string;
  url?: string;
  format?: string;
};
export type ActionProposal = {
  id: string;
  revision: number;
  payload_digest: string;
  readback: string;
  status: string;
  expires_at: string;
};
export type Message = {
  id?: Identifier;
  role: string;
  content: string;
  created_at?: string;
  citations?: Citation[];
  artifacts?: Artifact[];
  job_id?: Identifier | null;
  approval_needed?: unknown;
  action_proposals?: ActionProposal[];
  search_suggestions_html?: string[];
  handled_by?: string;
};
export type Conversation = { id: Identifier; title: string; created_at: string; messages?: Message[] };
export type Turn = {
  reply_text: string;
  conversation_id: Identifier;
  command_id?: string;
  status?: string;
  citations: Citation[];
  artifacts: Artifact[];
  job_id?: Identifier | null;
  approval_needed?: unknown;
  action_proposals?: ActionProposal[];
  search_suggestions_html?: string[];
};
export type CommandResult = {
  command_id: string;
  conversation_id: string;
  request_id: string;
  input_text: string;
  channel: string;
  status: string;
  response: Turn;
  error: string;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  actions?: { id: string; tool: string; status: string; result: { message?: string } }[];
  proposals?: ActionProposal[];
};
export type Schedule = {
  kind: 'once' | 'daily' | 'weekly';
  at?: string;
  time?: string;
  weekdays?: number[];
  timezone: string;
};
export type ScheduledTask = {
  id: Identifier;
  revision?: string;
  name: string;
  kind: string;
  payload: {
    message?: string;
    query?: string;
    topic?: string;
    report_kind?: string;
    include_academic?: boolean;
  };
  schedule: Schedule;
  enabled?: boolean;
  paused?: boolean;
  status?: string;
  next_run_at?: string | null;
  created_at: string;
};
export type WorkflowDefinition = {
  name: string;
  description: string;
  steps: { tool: string; args: Record<string, unknown> }[];
  allowed_tools: string[];
  allowed_domains: string[];
  allowed_paths: string[];
  trigger: Record<string, unknown>;
};
export type Workflow = WorkflowDefinition & {
  id: Identifier;
  enabled?: boolean;
  status?: string;
  paused?: boolean;
  created_at: string;
};
export type Run = {
  id: Identifier;
  status: string;
  kind?: string;
  workflow?: Identifier;
  workflow_name?: string;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  result?: unknown;
  error?: string;
  payload?: unknown;
};
export type Approval = {
  id: Identifier;
  status: string;
  reason?: string;
  action?: string;
  tool?: string;
  payload?: unknown;
  details?: unknown;
  created_at: string;
};
export type Report = {
  id: Identifier;
  title: string;
  created_at: string;
  status?: string;
  citations?: Citation[];
  summary?: string;
  error?: string;
  progress?: {
    stage: string;
    label: string;
    current?: number;
    total?: number;
    updated_at?: string;
    telegram_delivery?: { status: string; error?: string; sent_at?: string };
  };
  report_kind?: string;
  files?: { pdf: boolean; docx: boolean };
  content?: Record<string, unknown>;
};
export type Notification = {
  id: string;
  text: string;
  status: string;
  created_at: string;
  read_at?: string | null;
  error?: string;
};
export type RuntimeStatus = {
  mode: string;
  managed: boolean;
  stopping?: boolean;
  voice_shortcut?: string | null;
  start_at_login?: boolean | null;
  supervisor_status?: string;
  issues?: Record<string, string>;
  backup?: { status?: string; created_at?: string; encrypted?: boolean; bytes?: number; reason?: string; verified?: boolean; files?: number; format?: number; scope?: string };
  note: string;
  services: { id: string; title: string; status: string; last_seen?: string; task_started_at?: string }[];
};
export type Audit = {
  id: Identifier;
  action: string;
  created_at: string;
  details?: unknown;
  metadata?: unknown;
  actor?: string;
};
export type Device = {
  id: Identifier;
  name: string;
  last_seen_at?: string | null;
  last_seen?: string | null;
  active?: boolean;
  created_at: string;
  credential?: string;
};
export type Integration =
  | boolean
  | { configured?: boolean; connected?: boolean; enabled?: boolean; status?: string };
export type SystemStatus = {
  paused: boolean;
  desktop_online: boolean;
  scheduler_online?: boolean;
  scheduler_last_seen?: string;
  timezone: string;
  integrations: Record<string, Integration>;
  runtime?: RuntimeStatus;
  active_commands?: number;
  pending_confirmations?: number;
  unread_notifications?: number;
  language_model?: { provider: string; model: string; local: boolean; web_search: string; research_model?: string | null };
  usage?: unknown;
};
export type CalendarEvent = {
  id: string;
  summary?: string;
  start?: { dateTime?: string; date?: string };
  end?: { dateTime?: string; date?: string };
  htmlLink?: string;
};
