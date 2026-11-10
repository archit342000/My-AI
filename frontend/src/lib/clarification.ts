/** A question the model (or a tool such as the code runner) asks the user while its turn waits. */
export interface ClarificationRequest {
  /** The id of the tool call the callback is registered under: the answer is posted with it. */
  id: string;
  question: string;
  options: string[];
}

/** The tool whose repeated call chunk carries a pending request. */
export const CLARIFICATION_TOOL = 'request_clarification';

const FALLBACK_QUESTION = 'The assistant needs your input.';

/**
 * Reads the arguments the server sends with a request: `{ "question": ..., "options": [...] }`. Arguments that
 * do not parse give a fixed question and no options, so a bad payload still shows a prompt that can be answered.
 */
export function parseClarification(id: string, args: string): ClarificationRequest {
  try {
    const parsed: unknown = JSON.parse(args);
    if (parsed && typeof parsed === 'object') {
      const { question, options } = parsed as { question?: unknown; options?: unknown };
      return {
        id,
        question: typeof question === 'string' && question.trim() ? question : FALLBACK_QUESTION,
        options: Array.isArray(options)
          ? options.filter((o): o is string => typeof o === 'string' && o.trim().length > 0)
          : [],
      };
    }
  } catch {
    /* fall through to the fixed question */
  }
  return { id, question: FALLBACK_QUESTION, options: [] };
}
