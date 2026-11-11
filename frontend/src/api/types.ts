/** Server shapes used by the read path. Fields mirror `/api/chats` responses. */

/** The API sometimes stores absent values as the string "None"; treat those as empty. */
export type Nullable<T> = T | null | undefined;

export interface ChatSummary {
  id: string;
  title: string | null;
  timestamp: number | string | null;
  workspace_id: Nullable<string>;
  workspace_name?: Nullable<string>;
  is_running?: boolean;
  is_custom_title?: number;
  last_model?: Nullable<string>;
}

/** A tool call as the API stores it (OpenAI shape). */
export interface StoredToolCall {
  id?: string;
  function?: { name?: string; arguments?: string };
}

export interface StoredMessage {
  id: string | number;
  chat_id: string;
  role: 'user' | 'assistant' | 'tool' | 'system' | 'event' | string;
  /** Plain text, or a JSON array string of content parts for multimodal user messages. */
  content: Nullable<string>;
  timestamp: Nullable<string | number>;
  model: Nullable<string>;
  /** Tool calls on assistant messages: a list, or a JSON string of one on older payloads. */
  tool_calls: Nullable<string | StoredToolCall[]>;
  tool_call_id: Nullable<string>;
  name: Nullable<string>;
  parent_id: Nullable<string>;
  parent_type: Nullable<string>;
  reasoning_content: Nullable<string>;
  /** File references sent with a user message (decoded list); absent or null on older rows. */
  attachments?: Nullable<unknown>;
  /** Collections anchored on this message or its tool calls; the `research_progress` one holds a `ResearchProgress`. */
  collections?: Nullable<StoredCollection[]>;
  /** Sub-agent rows woven into this assistant row by the server (events, text, tool calls). */
  sub_agent_history?: Nullable<StoredSubAgentRow[]>;
}

/** One step of a research plan, as the server reports its progress. */
export interface ResearchProgressStep {
  index: number;
  heading: string;
  state: 'pending' | 'running' | 'done' | 'failed';
  /** Milliseconds the step took; null when the step is not done or its timestamps are missing. */
  duration_ms: Nullable<number>;
}

/** The research plan card's data: sent as a `research_progress` stream chunk and stored (and served) as a collection. */
export interface ResearchProgress {
  title: string;
  phase:
    | 'scouting'
    | 'planning'
    | 'awaiting_approval'
    | 'executing'
    | 'synthesizing'
    | 'done'
    | 'failed';
  steps: ResearchProgressStep[];
  steps_done: number;
  steps_total: number;
  pages_read: number;
}

/** A stored collection attached to an assistant message; `items` is the decoded value or its JSON string. */
export interface StoredCollection {
  collection_type: string;
  parent_type?: Nullable<string>;
  parent_message_id?: Nullable<string | number>;
  items?: unknown;
}

/** A sub-agent row inside an assistant message's `sub_agent_history`. */
export interface StoredSubAgentRow {
  id?: string | number;
  agent_name?: Nullable<string>;
  /** `event`, `assistant` or `tool`. */
  role: string;
  content?: Nullable<string>;
  reasoning_content?: Nullable<string>;
  tool_calls?: Nullable<string | StoredToolCall[]>;
  tool_call_id?: Nullable<string>;
  /** The assistant row id, or the id of the tool call that started the sub-agent. */
  parent_message_id?: Nullable<string | number>;
  sequence_order?: Nullable<number>;
}

export interface ChatDetail extends ChatSummary {
  messages: StoredMessage[];
  message_order_map?: string;
  /** True when a turn was interrupted and can be continued (false while one runs or after a stop). */
  resume_needed?: boolean;
  file_system_mode?: number;
  /** The chat's own settings, as the server stores them (numbers 0/1 for flags; "None" for unset). */
  persona_id?: Nullable<string>;
  research_mode?: Nullable<number | boolean>;
  browsing_mode?: Nullable<number | boolean>;
  git_mode?: Nullable<number | boolean>;
  code_execution_mode?: Nullable<number | boolean>;
  user_preferences?: Nullable<number | boolean>;
  max_tokens?: Nullable<number | string>;
  thinking_budget_tokens?: Nullable<number | string>;
  thinking_profile?: Nullable<string>;
  enable_thinking?: Nullable<number | boolean>;
  temperature?: Nullable<number | string>;
  top_p?: Nullable<number | string>;
}

export interface Workspace {
  id: string;
  name: string;
  icon: Nullable<string>;
  timestamp: number | null;
}
