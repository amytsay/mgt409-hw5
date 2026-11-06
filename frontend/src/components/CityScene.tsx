// The 3D city: a CSS-3D ground plane with extruded neon buildings, a stacked-layer car, a chase camera,
// AI traffic, a GPS route line, a speedometer and a minimap. Everything that moves is updated
// imperatively in one requestAnimationFrame loop (no React re-render per frame).
import { Fragment, forwardRef, memo, useEffect, useImperativeHandle, useMemo, useRef } from "react";
import { AVENUES, PLACES, STREETS, WORLD, buildCity, pathLength, route, type Place, type Point } from "../city";

export type CamMode = "chase" | "map";
export type PlaceState = "idle" | "active" | "visited" | "open" | "selected" | "running" | "resolved" | "needs";

export interface CitySceneHandle {
  driveTo: (placeId: string) => void;
  celebrate: () => void;
  clearQueue: () => void;
}

interface Props {
  mode: CamMode;
  placeStates: Record<string, PlaceState>;
  bubbles: Record<string, string | undefined>;
  onArrive?: (placeId: string) => void;
  onPlaceClick?: (placeId: string) => void;
  onDriveState?: (s: { driving: boolean; dest: string | null; nitro: boolean }) => void;
}

const BASE_SPEED = 430;  // world px / s
const ACCEL = 520;
const DECEL = 700;
const MPH = 0.16;

const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
function lerpAngle(a: number, b: number, k: number) {
  let d = ((b - a + 540) % 360) - 180;
  if (d < -180) d += 360;
  return a + d * k;
}

// ---------- static pieces ----------

const Box = memo(function Box(p: { x: number; y: number; w: number; d: number; h: number; color: string;
  className?: string; children?: React.ReactNode }) {
  const style = { left: p.x, top: p.y, width: p.w, height: p.d, "--c": p.color } as React.CSSProperties;
  return (
    <div className={`box ${p.className ?? ""}`} style={style}>
      <div className="face roof" style={{ width: p.w, height: p.d, transform: `translateZ(${p.h}px)` }}>{p.children}</div>
      <div className="face wall ns" style={{ width: p.w, height: p.h, top: 0 }} />
      <div className="face wall ns" style={{ width: p.w, height: p.h, top: p.d }} />
      <div className="face wall ew" style={{ width: p.h, height: p.d, left: 0 }} />
      <div className="face wall ew" style={{ width: p.h, height: p.d, left: p.w }} />
    </div>
  );
});

function Billboard({ x, y, z, className, children, onClick, label }: {
  x: number; y: number; z: number; className?: string; children: React.ReactNode; onClick?: () => void; label?: string;
}) {
  return (
    <div className="billboard-anchor" style={{ left: x, top: y, transform: `translateZ(${z}px)` }}>
      <div className="billboard-face">
        {onClick ? (
          <button type="button" className={`billboard ${className ?? ""}`} onClick={onClick} aria-label={label}>{children}</button>
        ) : (
          <div className={`billboard ${className ?? ""}`}>{children}</div>
        )}
      </div>
    </div>
  );
}

const Ground = memo(function Ground({ parks, trees }: { parks: ReturnType<typeof buildCity>["parks"]; trees: ReturnType<typeof buildCity>["trees"] }) {
  const R = 30;
  const top = STREETS[STREETS.length - 1].y + R;
  return (
    <svg className="ground" width={WORLD.w} height={WORLD.h} viewBox={`0 0 ${WORLD.w} ${WORLD.h}`} aria-hidden="true">
      <defs>
        <linearGradient id="water" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1b0f3d" />
          <stop offset="1" stopColor="#071a33" />
        </linearGradient>
        <pattern id="ripples" width="80" height="24" patternUnits="userSpaceOnUse">
          <path d="M0 12 Q20 4 40 12 T80 12" fill="none" stroke="#35f0ff" strokeOpacity="0.18" strokeWidth="2" />
        </pattern>
        <radialGradient id="tree" cx="0.4" cy="0.4">
          <stop offset="0" stopColor="#5dffb0" />
          <stop offset="1" stopColor="#0c5a3a" />
        </radialGradient>
      </defs>
      <rect x="0" y="0" width={WORLD.w} height={WORLD.h} fill="#0b0912" />
      {/* harbor */}
      <rect x="0" y={top + 14} width={WORLD.w} height={WORLD.h - top} fill="url(#water)" />
      <rect className="ripples" x="-80" y={top + 20} width={WORLD.w + 160} height={WORLD.h - top} fill="url(#ripples)" />
      <text x={WORLD.w / 2} y={WORLD.h - 40} className="harbor-label">LONG WHARF · NEW HAVEN HARBOR</text>
      {/* parks */}
      {parks.map((p, i) => (
        <g key={i}>
          <rect x={p.x} y={p.y} width={p.w} height={p.h} rx="10" fill="#0d261c" stroke="#3dffa8" strokeOpacity="0.35" />
          <text x={p.x + p.w / 2} y={p.y + p.h / 2} className="park-label">THE GREEN</text>
        </g>
      ))}
      {/* roads */}
      {STREETS.map((s) => (
        <g key={s.name}>
          <rect x="0" y={s.y - R} width={WORLD.w} height={R * 2} fill="#16131f" />
          <line x1="0" x2={WORLD.w} y1={s.y - R} y2={s.y - R} className="curb" />
          <line x1="0" x2={WORLD.w} y1={s.y + R} y2={s.y + R} className="curb" />
          <line x1="0" x2={WORLD.w} y1={s.y} y2={s.y} className="lane" />
        </g>
      ))}
      {AVENUES.map((a) => (
        <g key={a.name}>
          <rect x={a.x - R} y="0" width={R * 2} height={top} fill="#16131f" />
          <line y1="0" y2={top} x1={a.x - R} x2={a.x - R} className="curb" />
          <line y1="0" y2={top} x1={a.x + R} x2={a.x + R} className="curb" />
          <line y1="0" y2={top} x1={a.x} x2={a.x} className="lane" />
        </g>
      ))}
      {/* intersections: clear the lane paint, add crosswalks */}
      {AVENUES.flatMap((a) => STREETS.map((s) => (
        <g key={`${a.x}-${s.y}`}>
          <rect x={a.x - R} y={s.y - R} width={R * 2} height={R * 2} fill="#1a1624" />
          <rect x={a.x - R} y={s.y - R - 10} width={R * 2} height="8" className="xwalk" />
          <rect x={a.x - R} y={s.y + R + 2} width={R * 2} height="8" className="xwalk" />
        </g>
      )))}
      {STREETS.map((s) => [240, 960, 1290].map((x) => (
        <text key={`${s.name}-${x}`} x={x} y={s.y + 6} className="street-label">{s.name}</text>
      )))}
      {AVENUES.map((a) => [280, 840].map((y) => (
        <text key={`${a.name}-${y}`} x={a.x} y={y} className="street-label" transform={`rotate(-90 ${a.x} ${y})`} dy="6">{a.name}</text>
      )))}
      {trees.map((t, i) => <circle key={i} cx={t.x} cy={t.y} r={t.r} fill="url(#tree)" opacity="0.9" />)}
    </svg>
  );
});

// AI traffic: little cars looping around city blocks.
const TRAFFIC_LOOPS: { pts: Point[]; color: string; speed: number; offset: number }[] = [
  { pts: [{ x: 160, y: 420 }, { x: 1440, y: 420 }, { x: 1440, y: 700 }, { x: 160, y: 700 }], color: "#35f0ff", speed: 150, offset: 0 },
  { pts: [{ x: 480, y: 140 }, { x: 1120, y: 140 }, { x: 1120, y: 960 }, { x: 480, y: 960 }], color: "#b26bff", speed: 190, offset: 900 },
  { pts: [{ x: 1440, y: 960 }, { x: 160, y: 960 }, { x: 160, y: 140 }, { x: 1440, y: 140 }], color: "#ff9f43", speed: 170, offset: 1600 },
  { pts: [{ x: 800, y: 140 }, { x: 800, y: 960 }, { x: 1120, y: 960 }, { x: 1120, y: 140 }], color: "#3dffa8", speed: 140, offset: 300 },
];

function pointOnLoop(pts: Point[], dist: number): { p: Point; heading: number } {
  const closed = [...pts, pts[0]];
  const total = pathLength(closed);
  let d = ((dist % total) + total) % total;
  for (let i = 1; i < closed.length; i++) {
    const a = closed[i - 1], b = closed[i];
    const seg = Math.hypot(b.x - a.x, b.y - a.y);
    if (d <= seg) {
      const t = d / seg;
      return { p: { x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t) }, heading: (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI };
    }
    d -= seg;
  }
  return { p: pts[0], heading: 0 };
}

function CarModel({ color, small }: { color: string; small?: boolean }) {
  return (
    <div className={`car-model ${small ? "small" : ""}`} style={{ "--car": color } as React.CSSProperties}>
      <div className="car-shadow" />
      {!small && <div className="headlight-beam" />}
      {[0, 1, 2, 3, 4].map((i) => <div key={i} className="car-layer" style={{ transform: `translateZ(${i * 2.4}px)` }} />)}
      <div className="car-cabin" style={{ transform: `translateZ(${small ? 10 : 13}px)` }} />
      <div className="car-roof" style={{ transform: `translateZ(${small ? 13 : 17}px)` }} />
    </div>
  );
}

// ---------- the scene ----------

export const CityScene = forwardRef<CitySceneHandle, Props>(function CityScene(props, ref) {
  const { mode, placeStates, bubbles, onPlaceClick } = props;
  const viewport = useRef<HTMLDivElement>(null);
  const world = useRef<HTMLDivElement>(null);
  const car = useRef<HTMLDivElement>(null);
  const routeLine = useRef<SVGPolylineElement>(null);
  const miniRoute = useRef<SVGPolylineElement>(null);
  const miniCar = useRef<SVGGElement>(null);
  const speedText = useRef<HTMLSpanElement>(null);
  const speedArc = useRef<SVGPathElement>(null);
  const nitroEl = useRef<HTMLDivElement>(null);
  const npcRefs = useRef<(HTMLDivElement | null)[]>([]);
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const cb = useRef(props);
  cb.current = props;

  const city = useMemo(buildCity, []);
  const start = PLACES.hq;
  const sim = useRef({
    x: start.x, y: start.y, heading: -90, carHeading: -90, camHeading: -90, speed: 0,
    path: null as Point[] | null, seg: 0, dest: null as string | null, at: "hq", queue: [] as string[],
    spinUntil: 0, spinAngle: 0, nitro: false,
    cam: { cx: WORLD.w / 2, cy: WORLD.h / 2, rot: 0, tilt: 35, scale: 0.5, ay: 0.52 },
  });

  useImperativeHandle(ref, () => ({
    driveTo(placeId: string) {
      const s = sim.current;
      const last = s.queue.length ? s.queue[s.queue.length - 1] : (s.dest ?? s.at);
      if (last === placeId) return;
      s.queue.push(placeId);
      if (s.queue.length > 4) s.queue = s.queue.slice(-3);   // never fall too far behind the agents
    },
    celebrate() {
      sim.current.spinUntil = performance.now() + 2200;
    },
    clearQueue() {
      sim.current.queue = [];
    },
  }), []);

  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let lastHud = 0;
    let lastDrive = "";
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const setRoute = (pts: Point[] | null) => {
      const str = pts ? pts.map((p) => `${p.x},${p.y}`).join(" ") : "";
      routeLine.current?.setAttribute("points", str);
      miniRoute.current?.setAttribute("points", str);
    };

    const frame = (t: number) => {
      const dt = Math.min(0.05, (t - last) / 1000);
      last = t;
      const s = sim.current;

      // pick the next stop
      if (!s.path && s.queue.length) {
        const next = s.queue.shift()!;
        if (next !== s.at && PLACES[next]) {
          s.path = route({ x: s.x, y: s.y }, PLACES[next]);
          s.seg = 0;
          s.dest = next;
          setRoute(s.path);
        }
      }

      // drive
      if (s.path) {
        const rest = [{ x: s.x, y: s.y }, ...s.path.slice(s.seg + 1)];
        const remaining = pathLength(rest);
        s.nitro = s.queue.length > 0;
        const vmax = BASE_SPEED * (s.nitro ? 1.75 : 1);
        const target = Math.max(60, Math.min(vmax, Math.sqrt(2 * DECEL * remaining)));
        s.speed += Math.max(-DECEL * dt, Math.min(ACCEL * dt * (s.nitro ? 1.6 : 1), target - s.speed));
        let move = s.speed * dt;
        while (move > 0 && s.path) {
          const tgt = s.path[s.seg + 1];
          const dx = tgt.x - s.x, dy = tgt.y - s.y;
          const dist = Math.hypot(dx, dy);
          if (dist > 0.01) s.heading = (Math.atan2(dy, dx) * 180) / Math.PI;
          if (dist <= move) {
            s.x = tgt.x; s.y = tgt.y; move -= dist; s.seg++;
            if (s.seg >= s.path.length - 1) {
              const arrived = s.dest!;
              s.path = null; s.at = arrived; s.dest = null; s.speed = 0; s.nitro = false;
              setRoute(null);
              cb.current.onArrive?.(arrived);
            }
          } else {
            s.x += (dx / dist) * move; s.y += (dy / dist) * move; move = 0;
          }
        }
      } else {
        s.speed = Math.max(0, s.speed - DECEL * dt);
      }

      s.carHeading = lerpAngle(s.carHeading, s.heading, 1 - Math.exp(-dt * 12));
      s.camHeading = lerpAngle(s.camHeading, s.carHeading, 1 - Math.exp(-dt * 2.6));
      if (t < s.spinUntil && !reduced) s.spinAngle += 820 * dt;
      else s.spinAngle = lerpAngle(s.spinAngle, 0, 1 - Math.exp(-dt * 6));

      // camera
      const vp = viewport.current;
      const W = vp?.clientWidth ?? 1200, H = vp?.clientHeight ?? 700;
      if (vp && vp.dataset.h !== String(H)) { vp.dataset.h = String(H); vp.style.perspective = `${Math.round(H * 0.9)}px`; }
      const chase = modeRef.current === "chase" && !reduced;
      // city view: fit the map into the gap between the side panels (they overlay the scene on wide screens)
      const usableW = W > 1180 ? W - 780 : W;
      const fit = Math.min(usableW / WORLD.w, (H - 160) / WORLD.h) * 1.3;
      const tgt = chase
        ? { cx: s.x, cy: s.y, rot: -90 - s.camHeading, tilt: 73, scale: Math.max(1.0, Math.min(1.45, W / 1000)), ay: 0.76 }
        : { cx: WORLD.w / 2, cy: WORLD.h / 2 + 30, rot: 0, tilt: 30, scale: fit, ay: 0.56 };
      const c = s.cam;
      const k = 1 - Math.exp(-dt * (chase ? 5 : 3));
      c.cx = lerp(c.cx, tgt.cx, chase ? 1 - Math.exp(-dt * 9) : k);
      c.cy = lerp(c.cy, tgt.cy, chase ? 1 - Math.exp(-dt * 9) : k);
      c.rot = lerpAngle(c.rot, tgt.rot, k);
      c.tilt = lerp(c.tilt, tgt.tilt, k);
      c.scale = lerp(c.scale, tgt.scale, k);
      c.ay = lerp(c.ay, tgt.ay, k);
      const w = world.current;
      if (w) {
        w.style.transform = `translate3d(${W / 2}px, ${H * c.ay}px, 0) rotateX(${c.tilt}deg) scale(${c.scale}) rotateZ(${c.rot}deg) translate3d(${-c.cx}px, ${-c.cy}px, 0)`;
        w.style.setProperty("--unrot", `${-c.rot}deg`);
        w.style.setProperty("--untilt", `${-c.tilt}deg`);
      }
      if (car.current) {
        car.current.style.transform = `translate3d(${s.x}px, ${s.y}px, 0) rotateZ(${s.carHeading + 90 + s.spinAngle}deg)`;
        car.current.classList.toggle("boost", s.nitro && !!s.path);
        car.current.classList.toggle("moving", !!s.path);
      }

      // traffic
      TRAFFIC_LOOPS.forEach((n, i) => {
        const el = npcRefs.current[i];
        if (!el) return;
        const { p, heading } = pointOnLoop(n.pts, n.offset + (t / 1000) * n.speed);
        // drive on the right-hand lane
        const rad = ((heading + 90) * Math.PI) / 180;
        el.style.transform = `translate3d(${p.x + Math.cos(rad) * 14}px, ${p.y + Math.sin(rad) * 14}px, 0) rotateZ(${heading + 90}deg)`;
      });

      // HUD (throttled)
      if (t - lastHud > 70) {
        lastHud = t;
        const mph = Math.round(s.speed * MPH);
        if (speedText.current) speedText.current.textContent = String(mph);
        if (speedArc.current) speedArc.current.style.strokeDashoffset = String(100 - Math.min(1, mph / 130) * 100);
        nitroEl.current?.classList.toggle("on", s.nitro && !!s.path);
        miniCar.current?.setAttribute("transform", `translate(${s.x} ${s.y}) rotate(${s.carHeading + 90})`);
        const ds = `${!!s.path}|${s.dest}|${s.nitro}`;
        if (ds !== lastDrive) {
          lastDrive = ds;
          cb.current.onDriveState?.({ driving: !!s.path, dest: s.dest, nitro: s.nitro });
        }
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, []);

  const landmarks = Object.values(PLACES).filter((p) => p.height > 0);
  const jobs = Object.values(PLACES).filter((p) => p.kind === "job");

  const buildingFor = (p: Place) => {
    const st = placeStates[p.id] ?? "idle";
    const bx = p.x + p.offset.x - p.footprint[0] / 2;
    const by = p.y + p.offset.y - p.footprint[1] / 2;
    return (
      <Fragment key={p.id}>
        <Box x={bx} y={by} w={p.footprint[0]} d={p.footprint[1]} h={p.height} color={p.color}
             className={`landmark state-${st}`}>
          <div className="roof-sign" style={{ color: p.color }}>{p.icon}</div>
        </Box>
        {/* the stop where the car parks */}
        <div className={`stop-ring state-${st}`} style={{ left: p.x, top: p.y, "--c": p.color } as React.CSSProperties} />
        <Billboard x={bx + p.footprint[0] / 2} y={by + p.footprint[1] / 2} z={p.height + 18}
                   className={`place-sign state-${st}`} onClick={onPlaceClick ? () => onPlaceClick(p.id) : undefined}
                   label={p.label}>
          <span className="sign-icon">{p.icon}</span>
          <span className="sign-text" style={{ color: p.color }}>{p.label}</span>
        </Billboard>
        {bubbles[p.id] && (
          <Billboard x={bx + p.footprint[0] / 2} y={by + p.footprint[1] / 2} z={p.height + 78} className="speech">
            <span style={{ borderColor: p.color }}>{bubbles[p.id]}</span>
          </Billboard>
        )}
      </Fragment>
    );
  };

  return (
    <div className={`scene mode-${mode}`} ref={viewport}>
      <div className="sky" aria-hidden="true">
        <div className="stars" />
        <div className="sun" />
        <svg className="skyline" viewBox="0 0 1200 120" preserveAspectRatio="none">
          {Array.from({ length: 46 }, (_, i) => {
            const h = 25 + ((i * 37) % 80);
            return <rect key={i} x={i * 26} y={120 - h} width={22} height={h} />;
          })}
        </svg>
      </div>

      <div className="world" ref={world} style={{ width: WORLD.w, height: WORLD.h }}>
        <div className="ground-grid" />
        <Ground parks={city.parks} trees={city.trees} />
        <svg className="route-layer" width={WORLD.w} height={WORLD.h} aria-hidden="true">
          <polyline ref={routeLine} className="gps-route" points="" />
        </svg>
        {city.towers.map((t, i) => <Box key={i} x={t.x} y={t.y} w={t.w} d={t.d} h={t.h} color={t.hue} className="tower" />)}
        {landmarks.map(buildingFor)}
        {jobs.map((p) => {
          const st = placeStates[p.id] ?? "open";
          return (
            <Fragment key={p.id}>
              <div className={`job-ring state-${st}`} style={{ left: p.x, top: p.y }} />
              <Billboard x={p.x} y={p.y} z={4} className={`job-beam state-${st}`}><span /></Billboard>
              <Billboard x={p.x} y={p.y} z={150} className={`job-sign state-${st}`}
                         onClick={onPlaceClick ? () => onPlaceClick(p.id) : undefined} label={p.label}>
                <span className="sign-icon">{st === "resolved" ? "✅" : p.icon}</span>
                <span className="sign-text">{p.label}</span>
              </Billboard>
            </Fragment>
          );
        })}
        {TRAFFIC_LOOPS.map((n, i) => (
          <div key={i} className="car npc" ref={(el) => { npcRefs.current[i] = el; }}>
            <CarModel color={n.color} small />
          </div>
        ))}
        <div className="car player" ref={car}>
          <CarModel color="#ff3d9a" />
          <div className="nitro-flame" />
        </div>
      </div>

      <div className="haze" aria-hidden="true" />

      {/* racing HUD */}
      <div className="speedo" aria-hidden="true">
        <svg viewBox="0 0 120 120">
          <path d="M 25 95 A 50 50 0 1 1 95 95" className="speedo-track" pathLength={100} />
          <path ref={speedArc} d="M 25 95 A 50 50 0 1 1 95 95" className="speedo-fill" pathLength={100} />
        </svg>
        <div className="speedo-read"><span ref={speedText}>0</span><small>MPH</small></div>
        <div className="nitro" ref={nitroEl}>NITRO</div>
      </div>

      <svg className="minimap" viewBox={`0 0 ${WORLD.w} ${WORLD.h}`} role="img" aria-label="Minimap of Elm City">
        <rect width={WORLD.w} height={WORLD.h} fill="#0b0912" />
        <rect y={STREETS[STREETS.length - 1].y + 44} width={WORLD.w} height={200} fill="#0d1b3a" />
        {STREETS.map((s) => <line key={s.name} x1="0" x2={WORLD.w} y1={s.y} y2={s.y} className="mm-road" />)}
        {AVENUES.map((a) => <line key={a.name} y1="0" y2={STREETS[STREETS.length - 1].y} x1={a.x} x2={a.x} className="mm-road" />)}
        <polyline ref={miniRoute} className="mm-route" points="" />
        {Object.values(PLACES).map((p) => (
          <circle key={p.id} cx={p.x} cy={p.y} r={p.kind === "job" ? 34 : 28}
                  className={`mm-place state-${placeStates[p.id] ?? "idle"}`} fill={p.kind === "job" ? "#ff3d9a" : p.color} />
        ))}
        <g ref={miniCar}><path d="M0 -40 L28 34 L0 18 L-28 34 Z" fill="#fff" stroke="#ff3d9a" strokeWidth="8" /></g>
      </svg>
    </div>
  );
});
