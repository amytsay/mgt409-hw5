// The party: confetti + fireworks on a canvas, a "JOB COMPLETE" banner and the crew dancing.
import { useEffect, useRef } from "react";
import { CREW, CREW_ORDER } from "../crew";
import type { AgentName } from "../types";

const COLORS = ["#ff3d9a", "#35f0ff", "#ffd23f", "#3dffa8", "#b26bff", "#ff9f43", "#ffffff"];

interface Particle { x: number; y: number; vx: number; vy: number; life: number; max: number; color: string; size: number; spin: number; kind: "confetti" | "spark" }

export function Celebration({ title, subtitle, stats, crew, onDone }: {
  title: string; subtitle: string; stats: string[]; crew: AgentName[]; onDone: () => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const done = useRef(onDone);
  done.current = onDone;

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const cv = canvas.current!;
    const ctx = cv.getContext("2d")!;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const resize = () => { cv.width = innerWidth * dpr; cv.height = innerHeight * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); };
    resize();
    window.addEventListener("resize", resize);
    const parts: Particle[] = [];
    const rand = (a: number, b: number) => a + Math.random() * (b - a);

    const confetti = (n: number) => {
      for (let i = 0; i < n; i++) {
        parts.push({ x: rand(0, innerWidth), y: rand(-200, -10), vx: rand(-60, 60), vy: rand(120, 320), life: 0,
          max: rand(3, 5.5), color: COLORS[i % COLORS.length], size: rand(6, 12), spin: rand(0, 6), kind: "confetti" });
      }
    };
    const firework = () => {
      const x = rand(innerWidth * 0.15, innerWidth * 0.85), y = rand(innerHeight * 0.12, innerHeight * 0.45);
      const color = COLORS[Math.floor(rand(0, COLORS.length))];
      for (let i = 0; i < 70; i++) {
        const a = (i / 70) * Math.PI * 2, s = rand(120, 320);
        parts.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, life: 0, max: rand(0.9, 1.6), color, size: rand(2, 3.5), spin: 0, kind: "spark" });
      }
    };

    confetti(reduced ? 60 : 220);
    const timers = reduced ? [] : [0, 350, 800, 1300, 1700, 2300, 2900, 3500].map((ms) => setTimeout(firework, ms));
    const t2 = setTimeout(() => confetti(reduced ? 0 : 120), 1500);
    const end = setTimeout(() => done.current(), 6200);

    let raf = 0, last = performance.now();
    const frame = (t: number) => {
      const dt = Math.min(0.05, (t - last) / 1000);
      last = t;
      ctx.clearRect(0, 0, innerWidth, innerHeight);
      ctx.globalCompositeOperation = "lighter";
      for (let i = parts.length - 1; i >= 0; i--) {
        const p = parts[i];
        p.life += dt;
        if (p.life > p.max) { parts.splice(i, 1); continue; }
        p.vy += (p.kind === "spark" ? 160 : 40) * dt;
        p.vx *= p.kind === "spark" ? 0.985 : 1;
        p.x += p.vx * dt; p.y += p.vy * dt; p.spin += dt * 6;
        const alpha = 1 - p.life / p.max;
        ctx.globalAlpha = Math.max(0, alpha);
        ctx.fillStyle = p.color;
        if (p.kind === "confetti") {
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(p.spin);
          ctx.fillRect(-p.size / 2, -p.size / 4, p.size, (p.size / 2) * Math.abs(Math.cos(p.spin)));
          ctx.restore();
        } else {
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      timers.forEach(clearTimeout);
      clearTimeout(t2);
      clearTimeout(end);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <div className="party" role="status" aria-live="assertive" onClick={onDone}>
      <canvas ref={canvas} className="party-canvas" aria-hidden="true" />
      <div className="party-banner">
        <div className="party-kicker">{subtitle}</div>
        <div className="party-title">{title}</div>
        <div className="party-stats">{stats.map((s) => <span key={s}>{s}</span>)}</div>
        <div className="party-crew" aria-label="The crew celebrates">
          {(crew.length ? crew : CREW_ORDER).map((a, i) => (
            <span key={a} className="dancer" style={{ animationDelay: `${i * 0.12}s`, "--c": CREW[a].color } as React.CSSProperties}>
              <span className="dancer-icon">{CREW[a].icon}</span>
              <small>{CREW[a].callsign}</small>
            </span>
          ))}
        </div>
        <div className="party-hint">click anywhere to keep driving</div>
      </div>
    </div>
  );
}
