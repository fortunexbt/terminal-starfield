// Runs the unmodified terminal_starfield package on Pyodide, off the main thread.
import glue from './web_tty.py?raw';

const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/';
// Decoded sizes of the pinned release, used only to scale the progress bar.
const RUNTIME_FILES = { 'pyodide.asm.wasm': 9598218, 'python_stdlib.zip': 2545637, 'pyodide.asm.mjs': 1250344 };
const LOG_DIR = '/home/pyodide/.local/share/terminal-starfield';

const sources = import.meta.glob('../../terminal_starfield/*.py', { query: '?raw', import: 'default', eager: true });

let tty;
let pyodide;

const post = (message) => self.postMessage(message);

async function prefetch() {
  // Warm the HTTP cache with a byte count; loadPyodide then reads the same URLs from cache.
  const total = Object.values(RUNTIME_FILES).reduce((sum, size) => sum + size, 0);
  let received = 0;
  await Promise.all(Object.keys(RUNTIME_FILES).map(async (name) => {
    const response = await fetch(PYODIDE + name);
    if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
    const reader = response.body.getReader();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      received += value.byteLength;
      post({ type: 'progress', stage: 'download', received, total: Math.max(total, received) });
    }
  }));
}

function syncLog(populate) {
  return new Promise((resolve) => pyodide.FS.syncfs(populate, (error) => {
    if (error) post({ type: 'notice', text: 'Flight log is not saved in this browser.' });
    resolve();
  }));
}

async function boot(argv) {
  await prefetch();
  post({ type: 'progress', stage: 'start' });
  const { loadPyodide } = await import(/* @vite-ignore */ PYODIDE + 'pyodide.mjs');
  pyodide = await loadPyodide({ indexURL: PYODIDE, env: { HOME: '/home/pyodide' } });

  post({ type: 'progress', stage: 'install', modules: Object.keys(sources).length });
  pyodide.FS.mkdirTree(LOG_DIR);
  pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, {}, LOG_DIR);
  await syncLog(true);
  pyodide.FS.mkdirTree('/game/terminal_starfield');
  for (const [path, source] of Object.entries(sources)) {
    pyodide.FS.writeFile('/game/terminal_starfield/' + path.split('/').pop(), source);
  }
  pyodide.FS.writeFile('/game/web_tty.py', glue);
  pyodide.runPython("import sys; sys.path.insert(0, '/game')");

  post({ type: 'progress', stage: 'import' });
  start(argv);
}

function start(argv) {
  tty?.destroy();
  tty = pyodide.pyimport('web_tty').BrowserTTY(argv);
  post({ type: 'ready', open: tty.open() });
}

function tick({ input, cols, rows }) {
  const frame = tty.step(input, cols, rows);
  if (tty.log_changed()) syncLog(false);
  if (frame === undefined) {
    post({ type: 'exit', close: tty.close() });
    return;
  }
  post({ type: 'frame', frame });
}

self.onmessage = ({ data }) => {
  if (data.type === 'boot') {
    boot(data.argv).catch((error) => post({ type: 'error', message: String(error && error.message || error) }));
  } else if (data.type === 'restart') {
    start(data.argv);
  } else if (data.type === 'tick') {
    try {
      tick(data);
    } catch (error) {
      post({ type: 'error', message: String(error.message || error) });
    }
  }
};
