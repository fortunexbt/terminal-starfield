// Idle screen: a warp field in the game's CYAN//VOID palette that leans toward the pointer.
const STARS = 320;
const BANDS = 6;
const FAR = [55, 86, 130];
const NEAR = [210, 247, 255];
const ACCENT = [72, 238, 255];

function star(z = Math.random()) {
  return { x: Math.random() * 2 - 1, y: Math.random() * 2 - 1, z, px: null, py: null };
}

export function runAttract(canvas) {
  const context = canvas.getContext('2d');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const stars = Array.from({ length: STARS }, () => star());
  const lean = { x: 0, y: 0, tx: 0, ty: 0 };
  let width = 0;
  let height = 0;
  let frame = 0;
  let last = 0;
  let visible = true;
  let stopped = false;

  const resize = () => {
    const ratio = Math.min(devicePixelRatio || 1, 2);
    width = canvas.clientWidth;
    height = canvas.clientHeight;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    stars.forEach((s) => { s.px = null; });
    if (reduced.matches) draw(0);
  };

  function draw(dt) {
    context.fillStyle = 'rgba(2, 5, 10, 0.32)';
    context.fillRect(0, 0, width, height);
    lean.x += (lean.tx - lean.x) * Math.min(1, dt * 3);
    lean.y += (lean.ty - lean.y) * Math.min(1, dt * 3);
    const cx = width / 2 - lean.x * width * 0.18;
    const cy = height / 2 - lean.y * height * 0.18;
    const scale = Math.max(width, height) * 0.5;
    // One path per depth band keeps this to a handful of stroke calls per frame.
    const bands = Array.from({ length: BANDS }, () => new Path2D());
    for (const s of stars) {
      s.z -= dt * 0.28;
      if (s.z <= 0.03) Object.assign(s, star(1));
      const x = cx + (s.x / s.z) * scale;
      const y = cy + (s.y / s.z) * scale;
      if (x < -20 || x > width + 20 || y < -20 || y > height + 20) {
        Object.assign(s, star(1));
        continue;
      }
      const path = bands[Math.min(BANDS - 1, Math.floor((1 - s.z) * BANDS))];
      path.moveTo(s.px ?? x, s.py ?? y);
      path.lineTo(x + 0.1, y + 0.1);
      s.px = x;
      s.py = y;
    }
    bands.forEach((path, band) => {
      const near = (band + 0.5) / BANDS;
      const color = band === BANDS - 1 ? ACCENT : FAR.map((c, i) => Math.round(c + (NEAR[i] - c) * near));
      context.strokeStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${0.4 + near * 0.6})`;
      context.lineWidth = 0.8 + near * 2.2;
      context.stroke(path);
    });
  }

  const tick = (now) => {
    if (stopped || !visible) return;
    frame = requestAnimationFrame(tick);
    draw(last ? Math.min(0.05, (now - last) / 1000) : 0);
    last = now;
  };

  const start = () => {
    cancelAnimationFrame(frame);
    last = 0;
    if (!stopped && visible && !reduced.matches) frame = requestAnimationFrame(tick);
  };

  new ResizeObserver(resize).observe(canvas);
  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    start();
  }).observe(canvas);
  reduced.addEventListener('change', start);
  canvas.parentElement.addEventListener('pointermove', (event) => {
    const box = canvas.getBoundingClientRect();
    lean.tx = (event.clientX - box.left) / box.width * 2 - 1;
    lean.ty = (event.clientY - box.top) / box.height * 2 - 1;
  });

  return () => {
    stopped = true;
    cancelAnimationFrame(frame);
  };
}
