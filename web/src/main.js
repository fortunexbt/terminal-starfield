import '@fontsource/chakra-petch/latin-600.css';
import '@fontsource/ibm-plex-sans/latin-400.css';
import '@fontsource/ibm-plex-sans/latin-500.css';
import '@fontsource/ibm-plex-mono/latin-400.css';
import '@fontsource/ibm-plex-mono/latin-500.css';
import './style.css';
import { runAttract } from './attract.js';

const consoleEl = document.querySelector('.console');
const overlay = consoleEl.querySelector('[data-overlay]');
const boot = overlay.querySelector('.boot');
const bootLog = overlay.querySelector('.boot-log');
const meter = overlay.querySelector('.meter');
const ended = overlay.querySelector('.ended');
const status = consoleEl.querySelector('[data-status]');
const sizeLabel = consoleEl.querySelector('[data-size]');
const pad = consoleEl.querySelector('.pad');
const touch = matchMedia('(pointer: coarse)').matches;
const stopAttract = runAttract(consoleEl.querySelector('.attract'));

const PAD_KEYS = { enter: '\r', esc: '\x1b' };
let game = null;

function setState(state, label) {
  consoleEl.dataset.state = state;
  status.textContent = label;
}

function setProgress(fraction) {
  meter.style.setProperty('--progress', fraction.toFixed(3));
  meter.setAttribute('aria-valuenow', String(Math.round(fraction * 100)));
}

function logLine(text) {
  const line = document.createElement('li');
  line.textContent = text;
  bootLog.append(line);
  return line;
}

let downloadLine = null;
function onProgress(progress) {
  if (progress.stage === 'download') {
    const share = progress.received / progress.total;
    downloadLine ??= logLine('');
    downloadLine.textContent = `Fetching CPython 3.14 for WebAssembly  ${Math.floor(share * 100)}%`;
    setProgress(share * 0.8);
  } else if (progress.stage === 'start') {
    logLine('Starting the interpreter');
    setProgress(0.86);
  } else if (progress.stage === 'install') {
    logLine(`Copying terminal_starfield, ${progress.modules} modules`);
    setProgress(0.93);
  } else if (progress.stage === 'import') {
    logLine('Importing the game, opening the TTY');
    setProgress(0.98);
  }
}

function halt(message) {
  overlay.querySelector('.power').hidden = true;
  boot.hidden = false;
  logLine(`Launch failed: ${message}`).className = 'boot-error';
  logLine('Reload the page to try again. The game needs WebAssembly and module workers.');
  setState('error', 'Halted');
}

async function launch(mode) {
  if (consoleEl.dataset.state !== 'idle') {
    consoleEl.scrollIntoView({ block: 'start', behavior: 'smooth' });
    game?.focus();
    return;
  }
  setState('booting', 'Booting');
  document.querySelector('.actions .launch').textContent = 'Back to the game';
  document.querySelector('.actions .ghost').hidden = true;
  overlay.querySelector('.power').hidden = true;
  boot.hidden = false;
  setProgress(0);
  logLine('Requesting runtime from cdn.jsdelivr.net');
  const top = consoleEl.getBoundingClientRect().top;
  if (top < 0 || top > innerHeight * 0.4) consoleEl.scrollIntoView({ block: 'start', behavior: 'smooth' });

  const argv = touch ? ['--auto-fire'] : ['--mouse'];
  if (mode === 'demo') argv.push('--demo');
  const { startGame } = await import('./game.js');
  game = await startGame({
    host: consoleEl.querySelector('.term'),
    argv,
    touch,
    events: {
      onProgress,
      onSize: (cols, rows) => { sizeLabel.textContent = `${cols}×${rows}`; },
      onReady: () => {
        setProgress(1);
        stopAttract();
        boot.hidden = true;
        ended.hidden = true;
        pad.hidden = !touch;
        setState('live', mode === 'demo' ? 'Live · autopilot, any key takes over' : 'Live · Python 3.14 on WebAssembly');
      },
      onExit: () => {
        ended.hidden = false;
        setState('ended', 'Exited to shell');
        ended.querySelector('button').focus();
      },
      onNotice: (text) => logLine(text),
      onError: halt,
    },
  });
}

document.querySelectorAll('[data-launch]').forEach((button) => {
  button.addEventListener('click', () => launch(button.dataset.launch).catch((error) => halt(error.message)));
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && document.activeElement === document.body && consoleEl.dataset.state === 'idle') {
    event.preventDefault();
    launch().catch((error) => halt(error.message));
  }
});

ended.querySelector('[data-again]').addEventListener('click', () => {
  ended.hidden = true;
  setState('booting', 'Restarting');
  game.restart();
});

function bindPad(button) {
  const key = PAD_KEYS[button.dataset.key] ?? button.dataset.key;
  let delay = 0;
  let repeat = 0;
  const release = () => {
    clearTimeout(delay);
    clearInterval(repeat);
    button.classList.remove('held');
  };
  button.addEventListener('pointerdown', (event) => {
    event.preventDefault();
    button.setPointerCapture(event.pointerId);
    button.classList.add('held');
    game?.send(key);
    if ('repeat' in button.dataset) {
      // Matches a terminal's key repeat: a pause, then a steady stream.
      delay = setTimeout(() => { repeat = setInterval(() => game?.send(key), 45); }, 220);
    }
  });
  button.addEventListener('pointerup', release);
  button.addEventListener('pointercancel', release);
  button.addEventListener('lostpointercapture', release);
  button.addEventListener('click', (event) => {
    if (event.detail === 0) game?.send(key);
  });
}
pad.querySelectorAll('[data-key]').forEach(bindPad);

document.querySelectorAll('[data-copy]').forEach((button) => {
  button.addEventListener('click', async () => {
    await navigator.clipboard.writeText(button.dataset.copy);
    button.textContent = 'Copied';
    setTimeout(() => { button.textContent = 'Copy'; }, 1600);
  });
});
