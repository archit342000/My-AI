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

export interface StoredMessage {
  id: string | number;
  chat_id: string;
  role: 'user' | 'assistant' | 'tool' | 'system' | 'event' | string;
  /** Plain text, or a JSON array string of content parts for multimodal user messages. */
  content: Nullable<string>;
  timestamp: Nullable<string | number>;
  model: Nullable<string>;
  /** JSON array string of tool calls on assistant messages. */
  tool_calls: Nullable<string>;
  tool_call_id: Nullable<string>;
  name: Nullable<string>;
  parent_id: Nullable<string>;
  parent_type: Nullable<string>;
  reasoning_content: Nullable<string>;
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
