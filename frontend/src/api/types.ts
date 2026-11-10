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
  /** Sub-agent rows woven into this assistant row by the server (events, text, tool calls). */
  sub_agent_history?: Nullable<StoredSubAgentRow[]>;
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
}

export interface Workspace {
  id: string;
  name: string;
  icon: Nullable<string>;
  timestamp: number | null;
}
