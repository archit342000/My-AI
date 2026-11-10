// API responses recorded from the real backend with a scripted model (`e2e/stack/record-fixtures.mjs`).
// The JSON is cast to the app's types without a check: the server returns `tool_calls` as a list while
// `StoredMessage` declares a string, and that gap is what these fixtures exist to exercise.
import type { ChatDetail } from '../../../api/types';
import chatOneTool from './chat-one-tool.json';
import chatPlain from './chat-plain.json';
import chatThreeTools from './chat-three-tools.json';

export const plainChat = chatPlain as unknown as ChatDetail;
export const oneToolChat = chatOneTool as unknown as ChatDetail;
export const threeToolChat = chatThreeTools as unknown as ChatDetail;
