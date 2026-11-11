/**
 * The dot sphere and the night stars (Console at Rest rule book, Part 3).
 * Pure maths is exported for tests; `startParticles` owns the canvases, listeners and frame loop.
 */

export const PERSPECTIVE = 800;
/** The angle between neighbouring dots: spreads them evenly, so no part of the ball bunches up. */
export const GOLDEN_ANGLE = 2.399963229728653;
/** The sphere is drawn at 75% of its base radius. */
export const SIZE_FACTOR = 0.75;
/** A phone is narrower than this (rule book 5.1). */
export const PHONE_WIDTH = 600;

export interface Particle {
  ux: number;
  uy: number;
  uz: number;
  /** Distance from the centre as a share of the radius (0.55 to 1.45). */
  distRatio: number;
  /** Which of the five dot colours (`--dot-1` to `--dot-5`). */
  colorIndex: number;
  size: number;
}

export interface Point3 {
  x: number;
  y: number;
  z: number;
}

/** Dots placed by the golden angle with a jittered distance. `random` is injectable for tests. */
export function createParticles(count: number, random: () => number = Math.random): Particle[] {
  const particles: Particle[] = [];
  for (let i = 0; i < count; i++) {
    const phi = Math.acos(1 - (2 * (i + 0.5)) / count);
    const theta = i * GOLDEN_ANGLE;
    particles.push({
      ux: Math.cos(theta) * Math.sin(phi),
      uy: Math.sin(theta) * Math.sin(phi),
      uz: Math.cos(phi),
      distRatio: 1 + (random() - 0.5) * 0.9,
      colorIndex: Math.min(4, Math.floor(random() * 5)),
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

/** 600 dots on a computer, 250 on a phone or a touch device. */
export function particleCount(small: boolean): number {
  return small ? 250 : 600;
}

/** Base radius: 42% of the shorter side on a phone, otherwise the larger of 300 and 28% of it. */
export function particleRadius(width: number, height: number): number {
  const minDim = Math.min(width, height);
  return width < PHONE_WIDTH ? minDim * 0.42 : Math.max(300, minDim * 0.28);
}

/**
 * How far the ball is stretched along each axis. A true ball everywhere except a phone, where it
 * grows slightly along the longer side: 1 + (side / shorter side - 1) * 0.3, capped at 1.3.
 */
export function sphereStretch(width: number, height: number): { x: number; y: number } {
  if (width >= PHONE_WIDTH) return { x: 1, y: 1 };
  const minDim = Math.min(width, height);
  const along = (side: number) => Math.min(1.3, 1 + (side / minDim - 1) * 0.3);
  return { x: along(width), y: along(height) };
}

/** Alpha for a dot at depth `z`: nearer dots are stronger. */
export function particleAlpha(z: number, radius: number, isDark: boolean): number {
  return Math.min(isDark ? 0.98 : 0.92, Math.max(0.1, (z + radius) / (2 * radius) + 0.18));
}

export interface Star {
  x: number;
  y: number;
  r: number;
  alpha: number;
}

/** A still field of small stars, the same every time for a given size (seeded, not random). */
export function createStars(width: number, height: number): Star[] {
  let seed = 20261110;
  const next = () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const stars: Star[] = [];
  const count = Math.round((width * height) / 6500);
  for (let i = 0; i < count; i++) {
    stars.push({
      x: next() * width,
      y: next() * height,
      r: 0.4 + next() * 0.9,
      alpha: 0.3 + next() * 0.6,
    });
  }
  return stars;
}

export interface StartOptions {
  canvas: HTMLCanvasElement;
  /** A second canvas for the night stars. Its strength is set in CSS (`--stars`): none by day. */
  starCanvas?: HTMLCanvasElement | null;
  isDark: () => boolean;
  /** The five dot colours and the star colour, read from the shared values. */
  palette: () => { dots: string[]; star: string };
  /** True when the person asked for less motion: one frame is drawn and nothing moves. */
  reduceMotion?: () => boolean;
}

export interface SphereHandle {
  /** Stops the loop and removes all listeners. */
  stop: () => void;
  /** A wave through the sphere: the person sent or committed something. */
  ripple: (strength?: number) => void;
  /** A slow pulse while the app is working. */
  setBusy: (busy: boolean) => void;
  /** Reads the colours again and redraws (after a theme change). */
  refresh: () => void;
}

/** Starts the sphere. */
export function startParticles({
  canvas,
  starCanvas = null,
  isDark,
  palette,
  reduceMotion = () => false,
}: StartOptions): SphereHandle {
  const ctx = canvas.getContext('2d');
  if (!ctx)
    return {
      stop: () => undefined,
      ripple: () => undefined,
      setBusy: () => undefined,
      refresh: () => undefined,
    };
  const starCtx = starCanvas?.getContext('2d') ?? null;
  const isTouch = navigator.maxTouchPoints > 0 || 'ontouchstart' in window;

  let width = window.innerWidth;
  let height = window.innerHeight;
  let radius = 350;
  let stretch = { x: 1, y: 1 };
  let particles: Particle[] = [];
  let colours = palette();
  let mouseX = 0;
  let mouseY = 0;
  let mouseXLerp = 0;
  let mouseYLerp = 0;
  let targetX = width / 2;
  let targetY = height / 2;
  let followX = targetX;
  let followY = targetY;
  let rippleX = 0;
  let rippleStrength = 0;
  let spin = 0;
  let pulse = 0;
  let pulseTarget = 0;
  let last = 0;
  let frame = 0;
  let stopped = false;
  let resizeTimer: ReturnType<typeof setTimeout> | undefined;

  function drawStars() {
    if (!starCanvas || !starCtx) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    starCanvas.width = Math.round(width * dpr);
    starCanvas.height = Math.round(height * dpr);
    starCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    starCtx.clearRect(0, 0, width, height);
    starCtx.fillStyle = colours.star;
    for (const star of createStars(width, height)) {
      starCtx.globalAlpha = star.alpha;
      starCtx.beginPath();
      starCtx.arc(star.x, star.y, star.r, 0, Math.PI * 2);
      starCtx.fill();
    }
  }

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    const wasSmall = particles.length > 0 && particles.length === particleCount(true);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    radius = particleRadius(width, height);
    stretch = sphereStretch(width, height);
    targetX = width / 2;
    targetY = height / 2;
    const small = isTouch || width < PHONE_WIDTH;
    if (particles.length === 0 || small !== wasSmall)
      particles = createParticles(particleCount(small));
    drawStars();
  }

  function draw(now: number) {
    const dt = Math.min(64, now - (last || now));
    last = now;
    ctx!.clearRect(0, 0, width, height);
    mouseXLerp += (mouseX - mouseXLerp) * 0.05;
    mouseYLerp += (mouseY - mouseYLerp) * 0.05;
    followX += (targetX - followX) * 0.06;
    followY += (targetY - followY) * 0.06;
    pulse += (pulseTarget - pulse) * 0.04;
    spin += dt * 0.0001 * (1 + 2.5 * pulse);
    const size = radius * SIZE_FACTOR;
    const centerX = followX + Math.sin(now * 0.0006) * 40;
    const centerY = followY + Math.cos(now * 0.0008) * 30;
    const rotX = -mouseYLerp * 0.3;
    const rotY = spin + mouseXLerp * 0.4;
    const breathe = 1 + 0.05 * pulse * Math.sin(now * 0.006);

    if (rippleStrength > 0.01) {
      rippleStrength *= 0.99;
      rippleX += 2.5;
    } else {
      rippleStrength = 0;
      rippleX = 0;
    }

    const projected: Array<Point3 & { colorIndex: number; size: number }> = [];
    for (const p of particles) {
      const wave = Math.sin(now * 0.0015 + p.ux * 2 + p.uy * 2 + p.uz * 2) * 15;
      const rBase = (p.distRatio * size + wave) * breathe;
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
        x: r.x * scale * stretch.x + centerX,
        y: r.y * scale * stretch.y + centerY,
        z: r.z,
        colorIndex: p.colorIndex,
        size: p.size * scale * (0.6 + 0.4 * SIZE_FACTOR),
      });
    }
    projected.sort((a, b) => b.z - a.z);

    const dark = isDark();
    for (const p of projected) {
      ctx!.globalAlpha = particleAlpha(p.z, size, dark);
      ctx!.fillStyle = colours.dots[p.colorIndex] ?? colours.dots[0] ?? '';
      ctx!.beginPath();
      ctx!.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx!.fill();
    }
  }

  function animate(now: number) {
    if (stopped) return;
    draw(now);
    // Less motion: this frame stays as it is. A resize or a theme change draws one more.
    if (!reduceMotion()) frame = requestAnimationFrame(animate);
  }

  /** Draws one frame now, when no loop is running to do it. */
  function redrawStill() {
    if (!reduceMotion() || stopped) return;
    followX = targetX;
    followY = targetY;
    draw(performance.now());
  }

  function onPointerDown(e: PointerEvent) {
    if (reduceMotion()) return;
    followX += (e.clientX - followX) * 0.15;
    followY += (e.clientY - followY) * 0.15;
    targetX = e.clientX;
    targetY = e.clientY;
    rippleX = radius * SIZE_FACTOR * 0.3;
    rippleStrength = 1.3;
  }

  function onPointerMove(e: PointerEvent) {
    if (reduceMotion()) return;
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
      if (window.innerWidth !== width || window.innerHeight !== height) {
        resize();
        redrawStill();
      }
    }, 150);
  }

  function onTouchStart(e: TouchEvent) {
    e.preventDefault();
  }

  resize();
  window.addEventListener('pointerdown', onPointerDown, { passive: true });
  window.addEventListener('pointermove', onPointerMove, { passive: true });
  window.addEventListener('resize', onResize);
  canvas.addEventListener('touchstart', onTouchStart, { passive: false });
  frame = requestAnimationFrame(animate);

  return {
    stop: () => {
      stopped = true;
      cancelAnimationFrame(frame);
      clearTimeout(resizeTimer);
      window.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('resize', onResize);
      canvas.removeEventListener('touchstart', onTouchStart);
    },
    ripple: (strength = 1.3) => {
      if (reduceMotion()) return;
      rippleX = radius * SIZE_FACTOR * 0.3;
      rippleStrength = strength;
    },
    setBusy: (busy) => {
      pulseTarget = busy && !reduceMotion() ? 1 : 0;
    },
    refresh: () => {
      colours = palette();
      drawStars();
      redrawStill();
    },
  };
}
