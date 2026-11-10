// Starts the real backend against a scripted model, on a temporary data directory, for the stack e2e suite.
//   node e2e/stack/start-stack.mjs           runs until stopped (Playwright's webServer)
//   node e2e/stack/start-stack.mjs --check   starts, checks the stack answers, stops and cleans up
// Needs the repo's Python (venv/bin/python, or E2E_PYTHON) and a tokenizer in the local Hugging Face cache
// (E2E_TOKENIZER names it; the default is the one the proxy config uses). Nothing here starts or manages llama.cpp.
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { startModelStub } from './model-stub.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const appPort = Number(process.env.E2E_STACK_PORT ?? 5195);
const stubPort = Number(process.env.E2E_STUB_PORT ?? appPort + 1);
/** The repo's interpreter: venv/bin/python in this checkout or in a parent (a git worktree lives under the main checkout). */
function findPython() {
  for (let dir = root; dirname(dir) !== dir; dir = dirname(dir)) {
    const candidate = join(dir, 'venv/bin/python');
    if (existsSync(candidate)) return candidate;
  }
  return undefined;
}
const python = process.env.E2E_PYTHON ?? findPython();
if (!python)
  throw new Error('No Python found: set E2E_PYTHON to the repo interpreter (venv/bin/python).');
if (!existsSync(join(root, 'frontend/dist/index.html')))
  throw new Error('Build the frontend first: cd frontend && npm run build.');

const data = mkdtempSync(join(tmpdir(), 'myai-stack-'));
mkdirSync(join(data, 'chroma'), { recursive: true });
let stub;
let backend;
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  const finish = () => {
    stub?.close();
    rmSync(data, { recursive: true, force: true });
    process.exit(code);
  };
  if (!backend || backend.exitCode !== null) return finish();
  // Remove the data directory only after the backend has let go of its files.
  backend.once('exit', finish);
  backend.kill('SIGTERM');
  setTimeout(() => backend.kill('SIGKILL'), 5000).unref();
}
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => stop(0));

try {
  stub = await startModelStub(stubPort);
} catch (error) {
  console.error(`Could not start the model stub on :${stubPort}: ${error.message}`);
  stop(1);
}
backend = spawn(
  python,
  [
    '-c',
    `import app; app.app.run(host="127.0.0.1", port=${appPort}, use_reloader=False, threaded=True)`,
  ],
  {
    cwd: root,
    env: {
      ...process.env,
      PYTHONPATH: root,
      HF_HUB_OFFLINE: '1',
      DATA_DIR: data,
      CHROMA_PATH: join(data, 'chroma'),
      AI_PROXY_URL: `http://127.0.0.1:${stubPort}`,
      AUTH_PROVIDER: 'static',
      ADMIN_EMAIL: 'stack@test.io',
      FRONTEND: 'react',
    },
    stdio: ['ignore', 'inherit', 'inherit'],
  },
);

backend.on('error', (error) => {
  console.error(`Could not start the backend: ${error.message}`);
  stop(1);
});
backend.on('exit', (code) => {
  if (!stopping) {
    console.error(
      `The backend exited (${code}). Is the tokenizer in the local Hugging Face cache? Set E2E_TOKENIZER to one that is.`,
    );
    stop(1);
  }
});

async function waitFor(path) {
  for (let i = 0; i < 90; i++) {
    try {
      const response = await fetch(`http://127.0.0.1:${appPort}${path}`);
      if (response.ok) return response;
    } catch {
      // not up yet
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`The stack did not answer ${path} in time.`);
}

try {
  await waitFor('/api/version');
} catch (error) {
  console.error(error.message);
  stop(1);
}
console.log(`stack ready at http://127.0.0.1:${appPort} (data ${data})`);

if (process.argv.includes('--check')) {
  const me = await (await waitFor('/api/me')).json();
  const models = await (await waitFor('/api/models/')).json();
  console.log(
    `/api/me -> ${me.email} (${me.role}); /api/models/ -> ${models.data.map((m) => m.id).join(', ')}`,
  );
  stop(0);
}
