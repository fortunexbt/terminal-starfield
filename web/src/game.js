// xterm.js front end for the worker. Loaded only after the player presses Launch.
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

const FRAME_MS = 1000 / 61;

function fontSizeFor(width) {
  // About 100 columns on a laptop screen, and never smaller than 9px on a phone.
  return Math.max(9, Math.min(16, Math.floor(width / 60)));
}

export async function startGame({ host, argv, touch, events }) {
  await document.fonts.load('16px "IBM Plex Mono"');
  const term = new Terminal({
    fontFamily: '"IBM Plex Mono", ui-monospace, Menlo, monospace',
    fontSize: fontSizeFor(host.clientWidth),
    lineHeight: 1,
    convertEol: true,
    scrollback: 0,
    cursorBlink: false,
    theme: { background: '#02050a', foreground: '#d2f7ff', cursor: '#48eeff', selectionBackground: '#1d4a5c' },
  });
  const fit = new FitAddon();
  term.loadAddon(fit);
  term.open(host);
  // Tab leaves the terminal instead of being swallowed, so the page stays keyboard navigable.
  term.attachCustomKeyEventHandler((event) => event.key !== 'Tab');
  if (touch) term.textarea.setAttribute('inputmode', 'none');
  host.addEventListener('contextmenu', (event) => event.preventDefault());

  const resize = () => {
    term.options.fontSize = fontSizeFor(host.clientWidth);
    fit.fit();
    events.onSize(term.cols, term.rows);
  };
  const observer = new ResizeObserver(resize);
  observer.observe(host);
  resize();

  const worker = new Worker(new URL('./game.worker.js', import.meta.url), { type: 'module' });
  let input = '';
  let waiting = true;
  let last = 0;
  let live = false;

  const loop = (now) => {
    if (!live) return;
    requestAnimationFrame(loop);
    if (waiting || now - last < FRAME_MS) return;
    last = now;
    waiting = true;
    worker.postMessage({ type: 'tick', input, cols: term.cols, rows: term.rows });
    input = '';
  };

  const begin = (open) => {
    term.reset();
    term.write(`\x1b[38;2;105;139;156m$ starfield ${argv.join(' ')}\x1b[0m\r\n` + open);
    live = true;
    waiting = false;
    requestAnimationFrame(loop);
  };

  term.onData((data) => { input += data; });

  worker.onmessage = ({ data }) => {
    if (data.type === 'frame') {
      term.write('\x1b[H' + data.frame, () => { waiting = false; });
    } else if (data.type === 'progress') {
      events.onProgress(data);
    } else if (data.type === 'ready') {
      begin(data.open);
      events.onReady();
      term.focus();
    } else if (data.type === 'exit') {
      live = false;
      term.write(data.close + '\r\n');
      events.onExit();
    } else if (data.type === 'notice') {
      events.onNotice(data.text);
    } else if (data.type === 'error') {
      live = false;
      worker.terminate();
      events.onError(data.message);
    }
  };
  worker.onerror = (event) => {
    live = false;
    events.onError(event.message || 'The game worker failed to start.');
  };
  worker.postMessage({ type: 'boot', argv });

  return {
    send(data) { input += data; },
    restart() { worker.postMessage({ type: 'restart', argv }); },
    focus() { term.focus(); },
  };
}
