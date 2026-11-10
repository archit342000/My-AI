/**
 * Stored messages in the shape `GET /api/chats/<id>` returns (backend/database/wrapper
 * history_ops.py `get_woven_history`): a reply that uses tools is several assistant rows with
 * `tool_calls` as a list, one `tool` row per call, and sub-agent rows woven in as `sub_agent_history`.
 */
import type { StoredMessage } from '../../api/types';

function row(over: Partial<StoredMessage> & Pick<StoredMessage, 'id' | 'role'>): StoredMessage {
  return {
    chat_id: 'c1',
    content: '',
    timestamp: 1,
    model: null,
    tool_calls: null,
    tool_call_id: null,
    name: null,
    parent_id: null,
    parent_type: 'main',
    reasoning_content: null,
    ...over,
  };
}

const call = (id: string, name: string) => ({
  id,
  type: 'function',
  function: { name, arguments: '{}' },
});

/** One user message answered with no tool. */
export const noToolReply: StoredMessage[] = [
  row({ id: 1, role: 'user', content: 'hi' }),
  row({ id: 2, role: 'assistant', content: 'Hello!', model: 'M' }),
];

/** One user message answered after one tool round. */
export const oneToolReply: StoredMessage[] = [
  row({ id: 1, role: 'user', content: 'list' }),
  row({
    id: 2,
    role: 'assistant',
    content: 'Looking.',
    reasoning_content: 'need files',
    tool_calls: [call('t1', 'list_files')],
    model: 'M',
  }),
  row({ id: 3, role: 'tool', tool_call_id: 't1', content: 'a.txt' }),
  row({ id: 4, role: 'assistant', content: 'One file: a.txt.', model: 'M' }),
];

/** One user message answered after three tool rounds, followed by a second question. */
export const threeToolReply: StoredMessage[] = [
  row({ id: 1, role: 'user', content: 'dig' }),
  row({ id: 2, role: 'assistant', tool_calls: [call('t1', 'a')], model: 'M' }),
  row({ id: 3, role: 'tool', tool_call_id: 't1', content: 'r1' }),
  row({ id: 4, role: 'assistant', tool_calls: [call('t2', 'b')], model: 'M' }),
  row({ id: 5, role: 'tool', tool_call_id: 't2', content: 'r2' }),
  row({ id: 6, role: 'assistant', tool_calls: [call('t3', 'c')], model: 'M' }),
  row({ id: 7, role: 'tool', tool_call_id: 't3', content: 'r3' }),
  row({ id: 8, role: 'assistant', content: 'Done digging.', model: 'M' }),
  row({ id: 9, role: 'user', content: 'thanks' }),
  row({ id: 10, role: 'assistant', content: 'Welcome.', model: 'M' }),
];

/** Two tool calls in one round; each has sub-agent rows, plus an event row woven in. */
export const subAgentReply: StoredMessage[] = [
  row({ id: 1, role: 'user', content: 'research' }),
  row({
    id: 2,
    role: 'assistant',
    tool_calls: [call('s1', 'spawn_agent'), call('s2', 'spawn_agent')],
    model: 'M',
    sub_agent_history: [
      {
        id: 21,
        agent_name: 'second',
        role: 'assistant',
        content: 'two says',
        parent_message_id: 's2',
        sequence_order: 3,
      },
      {
        id: 22,
        agent_name: 'first',
        role: 'event',
        content: 'one started',
        parent_message_id: 's1',
        sequence_order: 1,
      },
      {
        id: 23,
        agent_name: 'first',
        role: 'assistant',
        content: 'one says',
        parent_message_id: 's1',
        sequence_order: 2,
      },
    ],
  }),
  row({ id: 3, role: 'tool', tool_call_id: 's1', content: 'R1' }),
  row({ id: 4, role: 'tool', tool_call_id: 's2', content: 'R2' }),
  row({ id: 5, role: 'event', content: 'summary phase' }),
  row({ id: 6, role: 'assistant', content: 'Summary.', model: 'M' }),
];
