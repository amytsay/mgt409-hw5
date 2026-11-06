// "Elm City" map: an original, stylized night-time street grid (loosely New Haven), in world pixels.
// Every place sits on an intersection, so the car can always drive along streets with an L-shaped route.

export const WORLD = { w: 1600, h: 1120 };

export const AVENUES = [
  { x: 160, name: "PARK ST" },
  { x: 480, name: "YORK ST" },
  { x: 800, name: "COLLEGE ST" },
  { x: 1120, name: "TEMPLE ST" },
  { x: 1440, name: "STATE ST" },
];
export const STREETS = [
  { y: 140, name: "ELM ST" },
  { y: 420, name: "CHAPEL ST" },
  { y: 700, name: "CROWN ST" },
  { y: 960, name: "WATER ST" },
];

export interface Point { x: number; y: number }

export interface Place extends Point {
  id: string;
  label: string;
  kind: "hq" | "agent" | "job";
  color: string;
  icon: string;
  height: number;       // building height for the 3D block
  footprint: [number, number];
  offset: Point;        // where the building sits relative to its intersection
}

export const PLACES: Record<string, Place> = {
  hq: { id: "hq", label: "CAMPUS CUSTOMS HQ", kind: "hq", x: 800, y: 420, color: "#ffd23f", icon: "🐶",
    height: 120, footprint: [150, 110], offset: { x: 110, y: -95 } },
  inventory: { id: "inventory", label: "THE STOCKROOM", kind: "agent", x: 160, y: 140, color: "#35f0ff", icon: "📦",
    height: 70, footprint: [170, 120], offset: { x: 120, y: 100 } },
  accounting: { id: "accounting", label: "LEDGER LOUNGE", kind: "agent", x: 1440, y: 140, color: "#3dffa8", icon: "💸",
    height: 150, footprint: [120, 120], offset: { x: -110, y: 100 } },
  facilities: { id: "facilities", label: "LEASE OFFICE", kind: "agent", x: 1440, y: 960, color: "#ff9f43", icon: "🔑",
    height: 90, footprint: [130, 110], offset: { x: -110, y: -100 } },
  customer_service: { id: "customer_service", label: "HOTLINE DINER", kind: "agent", x: 160, y: 960, color: "#ff3d9a",
    icon: "📞", height: 50, footprint: [170, 100], offset: { x: 120, y: -95 } },
  t101: { id: "t101", label: "JOB 101 · SPECIAL DELIVERY", kind: "job", x: 480, y: 700, color: "#ff3d9a", icon: "👕",
    height: 0, footprint: [0, 0], offset: { x: 0, y: 0 } },
  t102: { id: "t102", label: "JOB 102 · RENT DAY", kind: "job", x: 1120, y: 700, color: "#ff3d9a", icon: "🏠",
    height: 0, footprint: [0, 0], offset: { x: 0, y: 0 } },
  t103: { id: "t103", label: "JOB 103 · BULK DEAL", kind: "job", x: 800, y: 960, color: "#ff3d9a", icon: "🧥",
    height: 0, footprint: [0, 0], offset: { x: 0, y: 0 } },
};

/** Route along the street grid: an L through one corner (the longer leg first, like a real driver). */
export function route(from: Point, to: Point): Point[] {
  if (from.x === to.x || from.y === to.y) return [from, to];
  const horizontalFirst = Math.abs(to.x - from.x) >= Math.abs(to.y - from.y);
  const corner = horizontalFirst ? { x: to.x, y: from.y } : { x: from.x, y: to.y };
  return [from, corner, to];
}

export function pathLength(pts: Point[]): number {
  let d = 0;
  for (let i = 1; i < pts.length; i++) d += Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
  return d;
}

// A seeded random so the skyline is the same on every load.
function rng(seed: number) {
  return () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };
}

export interface Tower { x: number; y: number; w: number; d: number; h: number; hue: string }
export interface Tree { x: number; y: number; r: number }

const NEON = ["#ff3d9a", "#35f0ff", "#b26bff", "#ff9f43", "#3dffa8"];

/** Generic city blocks: a few towers per block, skipping the landmark lots and the harbor. */
export function buildCity(): { towers: Tower[]; trees: Tree[]; parks: { x: number; y: number; w: number; h: number }[] } {
  const r = rng(409);
  const towers: Tower[] = [];
  const trees: Tree[] = [];
  const parks: { x: number; y: number; w: number; h: number }[] = [];
  const xs = [0, ...AVENUES.map((a) => a.x), WORLD.w];
  const ys = [0, ...STREETS.map((s) => s.y)];
  const landmarkBoxes = Object.values(PLACES)
    .filter((p) => p.height > 0)
    .map((p) => ({ x: p.x + p.offset.x - p.footprint[0] / 2, y: p.y + p.offset.y - p.footprint[1] / 2,
      w: p.footprint[0], h: p.footprint[1] }));
  const hitsLandmark = (x: number, y: number, w: number, h: number) =>
    landmarkBoxes.some((b) => x < b.x + b.w + 20 && x + w > b.x - 20 && y < b.y + b.h + 20 && y + h > b.y - 20);

  for (let i = 0; i < xs.length - 1; i++) {
    for (let j = 0; j < ys.length - 1; j++) {
      const bx = xs[i] + 40, by = ys[j] + 40;
      const bw = xs[i + 1] - xs[i] - 80, bh = ys[j + 1] - ys[j] - 80;
      if (bw < 40 || bh < 40) continue;
      // The New Haven Green: one park block in the middle of town.
      if (i === 2 && j === 2) {
        parks.push({ x: bx, y: by, w: bw, h: bh });
        for (let k = 0; k < 16; k++) trees.push({ x: bx + 20 + r() * (bw - 40), y: by + 20 + r() * (bh - 40), r: 10 + r() * 10 });
        continue;
      }
      const n = 2 + Math.floor(r() * 3);
      for (let k = 0; k < n; k++) {
        const w = 50 + r() * 70, d = 45 + r() * 60;
        const x = bx + r() * Math.max(1, bw - w), y = by + r() * Math.max(1, bh - d);
        if (hitsLandmark(x, y, w, d)) continue;
        towers.push({ x, y, w, d, h: 30 + r() * (j === 0 ? 170 : 110), hue: NEON[Math.floor(r() * NEON.length)] });
      }
      for (let k = 0; k < 3; k++) {
        const x = bx + r() * bw, y = by + r() * bh;
        if (!hitsLandmark(x - 10, y - 10, 20, 20)) trees.push({ x, y, r: 7 + r() * 6 });
      }
    }
  }
  return { towers, trees, parks };
}
