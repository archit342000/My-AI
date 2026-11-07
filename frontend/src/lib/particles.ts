/**
 * Ambient 3D particle sphere, ported from legacy `bg-animation.js` with the same constants.
 * Pure math is exported for tests; `startParticles` owns the canvas, listeners and RAF loop.
 */

export const PERSPECTIVE = 800;
export const PARTICLE_COLORS = ['#2563EB', '#3B82F6', '#1E40AF', '#60A5FA', '#DBEAFE'] as const;

export interface Particle {
  ux: number;
  uy: number;
  uz: number;
  distRatio: number;
  color: string;
  size: number;
}

export interface Point3 {
  x: number;
  y: number;
  z: number;
}

/** Fibonacci-sphere distribution with jittered radius. `random` is injectable for tests. */
export function createParticles(count: number, radius: number, random: () => number = Math.random): Particle[] {
  const particles: Particle[] = [];
  for (let i = 0; i < count; i++) {
    const phi = Math.acos(-1 + (2 * i) / count);
    const theta = Math.sqrt(count * Math.PI) * phi;
    const dispersion = radius * 0.9;
    const r = radius + (random() - 0.5) * dispersion;
    particles.push({
      ux: Math.cos(theta) * Math.sin(phi),
      uy: Math.sin(theta) * Math.sin(phi),
      uz: Math.cos(phi),
      distRatio: r / radius,
      color: PARTICLE_COLORS[Math.floor(random() * PARTICLE_COLORS.length)] ?? PARTICLE_COLORS[0],
      size: 1.5 + random() * 2.5,
    });
  }
  return particles;
}

/** Rotates a point around the X axis by `ax`, then the Y axis by `ay`. */
export function rotatePoint(p: Point3, ax: number, ay: number): Point3 {
  const cosY = Math.cos(ay);
  const sinY = Math.sin(ay);
  const x1 = p.x * cosY - p.z * sinY;
  const z1 = p.x * sinY + p.z * cosY;
  const cosX = Math.cos(ax);
  const sinX = Math.sin(ax);
  const y2 = p.y * cosX - z1 * sinX;
  const z2 = p.y * sinX + z1 * cosX;
  return { x: x1, y: y2, z: z2 };
}

export function particleCount(isTouch: boolean): number {
  return isTouch ? 250 : 900;
}

export function particleRadius(width: number, height: number): number {
  const minDim = Math.min(width, height);
  return width <= 768 ? minDim * 0.38 : Math.max(300, minDim * 0.28);
}

/** Alpha for a particle at depth `z`, clamped the same way as the legacy code. */
export function particleAlpha(z: number, radius: number, isDark: boolean): number {
  return Math.min(isDark ? 0.98 : 0.92, Math.max(0.1, (z + radius) / (2 * radius) + 0.18));
}

export interface StartOptions {
  canvas: HTMLCanvasElement;
  isDark: () => boolean;
}

/** Starts the animation. Returns a cleanup that stops the loop and removes all listeners. */
export function startParticles({ canvas, isDark }: StartOptions): () => void {
  const ctx = canvas.getContext('2d');
  if (!ctx) return () => undefined;
  const isTouch = navigator.maxTouchPoints > 0 || 'ontouchstart' in window;
  const count = particleCount(isTouch);

  let width = window.innerWidth;
  let height = window.innerHeight;
  let radius = 350;
  let particles: Particle[] = [];
  let mouseX = 0;
  let mouseY = 0;
  let mouseXLerp = 0;
  let mouseYLerp = 0;
  let targetX = window.innerWidth / 2;
  let targetY = window.innerHeight / 2;
  let followX = targetX;
  let followY = targetY;
  let rippleX = 0;
  let rippleStrength = 0;
  let frame = 0;
  let stopped = false;
  let resizeTimer: ReturnType<typeof setTimeout> | undefined;

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    radius = particleRadius(width, height);
    targetX = width / 2;
    targetY = height / 2;
  }

  function animate() {
    if (stopped) return;
    ctx!.clearRect(0, 0, width, height);
    const time = Date.now();
    mouseXLerp += (mouseX - mouseXLerp) * 0.05;
    mouseYLerp += (mouseY - mouseYLerp) * 0.05;
    followX += (targetX - followX) * 0.06;
    followY += (targetY - followY) * 0.06;
    const centerX = followX + Math.sin(time * 0.0006) * 40;
    const centerY = followY + Math.cos(time * 0.0008) * 30;
    const rotX = -mouseYLerp * 0.3;
    const rotY = time * 0.0001 + mouseXLerp * 0.4;

    if (rippleStrength > 0.01) {
      rippleStrength *= 0.99;
      rippleX += 2.5;
    } else {
      rippleStrength = 0;
      rippleX = 0;
    }

    const projected: Array<Point3 & { color: string; size: number }> = [];
    for (const p of particles) {
      const wave = Math.sin(time * 0.0015 + p.ux * 2 + p.uy * 2 + p.uz * 2) * 15;
      const rBase = p.distRatio * radius + wave;
      let rx = p.ux * rBase;
      let ry = p.uy * rBase;
      let rz = p.uz * rBase;
      if (rippleStrength > 0) {
        const diff = Math.abs(rBase - rippleX);
        if (diff < 160) {
          const force = Math.exp(-Math.pow(diff / 75, 2)) * rippleStrength * 140;
          rx += p.ux * force;
          ry += p.uy * force;
          rz += p.uz * force;
        }
      }
      const r = rotatePoint({ x: rx, y: ry, z: rz }, rotX, rotY);
      const scale = PERSPECTIVE / (PERSPECTIVE + r.z);
      if (scale < 0) continue;
      projected.push({
        x: r.x * scale + centerX,
        y: r.y * scale + centerY,
        z: r.z,
        color: p.color,
        size: p.size * scale,
      });
    }
    projected.sort((a, b) => b.z - a.z);

    const dark = isDark();
    for (const p of projected) {
      ctx!.globalAlpha = particleAlpha(p.z, radius, dark);
      ctx!.fillStyle = p.color;
      ctx!.beginPath();
      ctx!.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx!.fill();
    }
    frame = requestAnimationFrame(animate);
  }

  function onPointerDown(e: PointerEvent) {
    followX += (e.clientX - followX) * 0.15;
    followY += (e.clientY - followY) * 0.15;
    targetX = e.clientX;
    targetY = e.clientY;
    rippleX = radius * 0.3;
    rippleStrength = 1.3;
  }

  function onPointerMove(e: PointerEvent) {
    mouseX = (e.clientX - window.innerWidth / 2) / (window.innerWidth / 2);
    mouseY = (e.clientY - window.innerHeight / 2) / (window.innerHeight / 2);
    targetX = e.clientX;
    targetY = e.clientY;
  }

  function onResize() {
    targetX = window.innerWidth / 2;
    targetY = window.innerHeight / 2;
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (window.innerWidth !== width || window.innerHeight !== height) resize();
    }, 150);
  }

  function onTouchStart(e: TouchEvent) {
    e.preventDefault();
  }

  resize();
  particles = createParticles(count, radius);
  window.addEventListener('pointerdown', onPointerDown, { passive: true });
  window.addEventListener('pointermove', onPointerMove, { passive: true });
  window.addEventListener('resize', onResize);
  canvas.addEventListener('touchstart', onTouchStart, { passive: false });
  frame = requestAnimationFrame(animate);

  return () => {
    stopped = true;
    cancelAnimationFrame(frame);
    clearTimeout(resizeTimer);
    window.removeEventListener('pointerdown', onPointerDown);
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('resize', onResize);
    canvas.removeEventListener('touchstart', onTouchStart);
  };
}
