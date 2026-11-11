// A scripted stand-in for the inference proxy, for the stack e2e suite. No dependencies.
// The scenario is picked by a keyword in the last user message:
//   NOTHINK plain answer, no reasoning · TOOL one tool round · MULTI three tool rounds · SLOW a long, slow reply
//   LONG a long markdown reply (headings, a table, code, a list) for long-answer checks
//   ERR the model call fails · anything else: reasoning and a short answer (after tool rounds: a summary).
import http from 'node:http';

export const MODEL = 'Stub/E2E-Model';
const TOKENIZER = process.env.E2E_TOKENIZER ?? 'Qwen/Qwen3.6-35B-A3B';

const LONG =
  `# Heading one

Some **bold**, *italic*, \`inline code\` and a [link](https://example.com).

## Table

| Name | Value | Notes |
|---|---|---|
| alpha | 1 | first |
| beta | 2 | second row with a rather long cell of text to force wrapping on phones |

## Code

\`\`\`python
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a  # a very long comment line that should scroll horizontally rather than wrap in the code block ok
\`\`\`

1. One
2. Two
   - nested a
   - nested b

> A blockquote line.

Inline math $e^{i\\pi}+1=0$ and block:

$$
\\int_0^1 x^2 dx = \\frac{1}{3}
$$

---

` +
  Array.from(
    { length: 8 },
    (_, i) => `Paragraph ${i + 1}: ${'lorem ipsum dolor sit amet '.repeat(12)}`,
  ).join('\n\n');

const textOf = (message) => {
  const content = message?.content;
  if (Array.isArray(content)) return content.map((part) => part?.text ?? '').join(' ');
  return content ?? '';
};

function pieces(kind, text, parts = 6) {
  const size = Math.max(1, Math.floor(text.length / parts));
  const out = [];
  for (let i = 0; i < text.length; i += size)
    out.push({ choices: [{ delta: { [kind]: text.slice(i, i + size) } }], model: MODEL });
  return out;
}

const toolCall = (name, args, round) => ({
  choices: [
    {
      delta: {
        tool_calls: [
          {
            index: 0,
            id: `call_${name}_${round}`,
            type: 'function',
            function: { name, arguments: JSON.stringify(args) },
          },
        ],
      },
    },
  ],
  model: MODEL,
});

/** The chunks and the delay between them for the messages of one request, or null for a failing call. */
export function script(messages) {
  let lastUser = 0;
  messages.forEach((m, i) => {
    if (m.role === 'user') lastUser = i;
  });
  const question = textOf(messages[lastUser]);
  const rounds = messages.slice(lastUser).filter((m) => m.role === 'tool').length;
  if (/\bERR\b/.test(question)) return null;
  if (question.includes('NOTHINK'))
    return { chunks: pieces('content', 'Plain answer with no reasoning.'), delay: 30 };
  if (question.includes('MULTI') && rounds < 3) {
    return {
      chunks: [
        ...pieces('reasoning_content', `Step ${rounds + 1}: I should call the tool again.`),
        ...pieces('content', `Interim note ${rounds + 1}. `),
        toolCall('get_time', {}, rounds),
      ],
      delay: 30,
    };
  }
  if (question.includes('TOOL') && rounds < 1) {
    return {
      chunks: [
        ...pieces('reasoning_content', 'The user wants the time. I will call get_time.'),
        toolCall('get_time', {}, rounds),
      ],
      delay: 30,
    };
  }
  if (question.includes('LONG')) {
    return {
      chunks: [
        ...pieces('reasoning_content', 'Thinking about a long answer. '.repeat(20), 20),
        ...pieces('content', LONG, 60),
      ],
      delay: 20,
    };
  }
  if (question.includes('SLOW')) {
    const body = Array.from(
      { length: 12 },
      (_, i) => `Slow paragraph ${i}. ${'word '.repeat(60)}`,
    ).join('\n\n');
    return {
      chunks: [
        ...pieces('reasoning_content', 'Slow thinking. '.repeat(10), 10),
        ...pieces('content', body, 40),
      ],
      delay: 400,
    };
  }
  return {
    chunks: [
      ...pieces('reasoning_content', 'Considering the question carefully. '.repeat(rounds ? 3 : 2)),
      ...pieces(
        'content',
        rounds ? `Final answer after ${rounds} tool call(s).` : 'Hello! This is the answer.',
      ),
    ],
    delay: 30,
  };
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const json = (res, status, body) => {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
};

async function completion(req, res) {
  let raw = '';
  for await (const part of req) raw += part;
  const body = JSON.parse(raw || '{}');
  const plan = script(body.messages ?? []);
  if (!plan) return json(res, 500, { error: { message: 'stub failure' } });
  if (!body.stream) {
    const content = plan.chunks.map((c) => c.choices[0].delta.content ?? '').join('');
    return json(res, 200, {
      choices: [
        { message: { role: 'assistant', content: content || 'Stub title' }, finish_reason: 'stop' },
      ],
      model: MODEL,
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
    });
  }
  res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' });
  for (const chunk of plan.chunks) {
    if (res.destroyed) return;
    await sleep(plan.delay);
    res.write(`data: ${JSON.stringify(chunk)}\n\n`);
  }
  res.write(
    `data: ${JSON.stringify({ choices: [{ delta: {}, finish_reason: 'stop' }], model: MODEL, usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 } })}\n\n`,
  );
  res.end('data: [DONE]\n\n');
}

export function startModelStub(port) {
  const server = http.createServer((req, res) => {
    const path = (req.url ?? '').split('?')[0];
    if (req.method === 'POST' && path === '/api/models/v1/chat/completions')
      return void completion(req, res);
    if (path === '/api/models/config') {
      return json(res, 200, {
        research: { main: MODEL },
        general: { text: MODEL, vision: MODEL, vision_small: MODEL, coder: MODEL },
        embedding: 'emb',
        embedding_tokenizer: 'google/embeddinggemma-300m',
        model_metadata: { [MODEL]: { context_window: 100000, tokenizer: TOKENIZER } },
      });
    }
    if (['/api/models/', '/api/models', '/api/models/v1/models'].includes(path)) {
      return json(res, 200, { data: [{ id: MODEL, status: { value: 'loaded' } }] });
    }
    return json(res, 404, { error: 'stub: not implemented' });
  });
  return new Promise((resolve) => server.listen(port, '127.0.0.1', () => resolve(server)));
}
