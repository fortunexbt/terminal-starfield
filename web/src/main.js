import '@fontsource/ibm-plex-sans/latin-400.css';
import '@fontsource/ibm-plex-sans/latin-500.css';
import '@fontsource/ibm-plex-mono/latin-400.css';
import '@fontsource/ibm-plex-mono/latin-500.css';
import '@fontsource/ibm-plex-mono/latin-600.css';
import './style.css';
import { runAttract } from './attract.js';

const consoleEl = document.querySelector('.console');
const overlay = consoleEl.querySelector('[data-overlay]');
const power = overlay.querySelector('.power');
const boot = overlay.querySelector('.boot');
const bootLog = overlay.querySelector('.boot-log');
const meter = overlay.querySelector('.meter');
const ended = overlay.querySelector('.ended');
const takeover = consoleEl.querySelector('[data-takeover]');
const status = document.querySelector('[data-status]');
const sizeLabel = document.querySelector('[data-size]');
const pad = consoleEl.querySelector('.pad');
const touch = matchMedia('(pointer: coarse)').matches;
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const saveData = navigator.connection?.saveData === true;
const stopAttract = runAttract(consoleEl.querySelector('.attract'));

const PAD_KEYS = { enter: '\r', esc: '\x1b' };
const PILOT_ARGV = touch ? ['--auto-fire'] : ['--mouse'];
const DEMO_ARGV = ['--demo'];
let game = null;
// "attract" while the autopilot flies and the page is waiting for a player.
let mode = null;

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
  power.hidden = true;
  takeover.hidden = true;
  boot.hidden = false;
  logLine(`Launch failed: ${message}`).className = 'boot-error';
  logLine('Reload the page to try again. The game needs WebAssembly and module workers.');
  setState('error', 'Halted');
}

function showLive() {
  if (mode === 'handover') {
    mode = 'pilot';
    game.restart(PILOT_ARGV);
    game.focus();
    return;
  }
  setProgress(1);
  stopAttract();
  boot.hidden = true;
  ended.hidden = true;
  takeover.hidden = mode !== 'attract';
  pad.hidden = !touch || mode === 'attract';
  const label = { attract: 'Autopilot demo', demo: 'Autopilot, any key takes over', pilot: 'Live, Python 3.14 on WebAssembly' };
  setState('live', label[mode]);
}

async function launch(next) {
  mode = next;
  setState('booting', 'Booting');
  power.hidden = true;
  boot.hidden = false;
  setProgress(0);
  logLine('Requesting runtime from cdn.jsdelivr.net');

  const { startGame } = await import('./game.js');
  game = await startGame({
    host: consoleEl.querySelector('.term'),
    argv: next === 'pilot' ? PILOT_ARGV : DEMO_ARGV,
    touch,
    events: {
      onProgress,
      onSize: (cols, rows) => { sizeLabel.textContent = `${cols}×${rows}`; },
      onReady: showLive,
      // The autopilot ignores the keyboard; the first key hands the ship to the player instead.
      onInput: () => {
        if (mode !== 'attract') return true;
        fly();
        return false;
      },
      onExit: () => {
        ended.hidden = false;
        takeover.hidden = true;
        setState('ended', 'Exited to shell');
        ended.querySelector('button').focus();
      },
      onNotice: (text) => logLine(text),
      onError: halt,
    },
  });
}

function fly() {
  if (consoleEl.dataset.state === 'idle') {
    launch('pilot').catch((error) => halt(error.message));
    return;
  }
  if (mode === 'attract' && consoleEl.dataset.state === 'booting') {
    // Still loading: skip the autopilot and open the flight deck as soon as Python is up.
    mode = 'handover';
    takeover.hidden = true;
    return;
  }
  if (mode === 'attract') {
    mode = 'pilot';
    takeover.hidden = true;
    status.textContent = 'Opening the flight deck';
    game.restart(PILOT_ARGV);
  }
  game.focus();
}

takeover.addEventListener('click', fly);

overlay.querySelectorAll('[data-launch]').forEach((button) => {
  button.addEventListener('click', () => {
    if (button.dataset.launch === 'demo') launch('demo').catch((error) => halt(error.message));
    else fly();
  });
});

document.addEventListener('keydown', (event) => {
  const idleFocus = document.activeElement === document.body;
  if (event.key === 'Enter' && idleFocus && (mode === 'attract' || consoleEl.dataset.state === 'idle')) {
    event.preventDefault();
    fly();
  }
});

ended.querySelector('[data-again]').addEventListener('click', () => {
  ended.hidden = true;
  mode = 'pilot';
  setState('booting', 'Restarting');
  game.restart(PILOT_ARGV);
  game.focus();
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

// The cabinet boots into its attract run unless the visitor asked for less motion or less data.
if (!reduced && !saveData) launch('attract').catch((error) => halt(error.message));
