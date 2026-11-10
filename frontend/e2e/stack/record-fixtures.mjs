// Records API fixtures from the real backend (scripted model), for src/test/fixtures/api/.
//   node e2e/stack/start-stack.mjs &      # then, in another shell:
//   node e2e/stack/record-fixtures.mjs
// Regenerate when the API shape changes. Ids and timestamps are kept as recorded.
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const base = `http://127.0.0.1:${process.env.E2E_STACK_PORT ?? 5195}`;
const out = join(dirname(fileURLToPath(import.meta.url)), '../../src/test/fixtures/api');
mkdirSync(out, { recursive: true });

async function turn(chatId, text) {
  const response = await fetch(`${base}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'Stub/E2E-Model',
      lastModelName: 'Stub/E2E-Model',
      chatId,
      messages: [{ role: 'user', content: text }],
      stream: true,
      max_tokens: 1024,
      thinking_budget_tokens: 0,
      enable_thinking: true,
      thinking_profile: 'general',
    }),
  });
  if (!response.ok)
    throw new Error(`completion failed: ${response.status} ${await response.text()}`);
  await response.text(); // read to the end: the turn is saved when the stream finishes
}

const save = async (name, path) => {
  const response = await fetch(`${base}${path}`);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  writeFileSync(join(out, `${name}.json`), `${JSON.stringify(await response.json(), null, 2)}\n`);
  console.log(`recorded ${name}`);
};

const chats = {
  'chat-plain': 'NOTHINK plain',
  'chat-one-tool': 'TOOL one round',
  'chat-three-tools': 'MULTI three rounds',
};
for (const [name, text] of Object.entries(chats)) {
  const id = `fixture-${name}`;
  await turn(id, text);
  await save(name, `/api/chats/${id}`);
}
