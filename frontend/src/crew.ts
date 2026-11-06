// The crew: each agent gets a callsign, a color, a home base on the map and its own "voice" on the radio.
import type { AgentName } from "./types";

export interface CrewMember {
  id: AgentName;
  callsign: string;
  role: string;
  icon: string;
  color: string;
  base: string;          // location id on the city map
  baseName: string;
  voice: string;         // CSS class that gives each agent a different look on the radio
  tagline: string;
}

export const CREW: Record<AgentName, CrewMember> = {
  boss: {
    id: "boss", callsign: "BIG DOG", role: "The Boss", icon: "🐶", color: "#ffd23f",
    base: "hq", baseName: "Campus Customs HQ", voice: "voice-boss",
    tagline: "Routes every job, signs off on anything over the line.",
  },
  inventory: {
    id: "inventory", callsign: "STACKS", role: "Inventory", icon: "📦", color: "#35f0ff",
    base: "inventory", baseName: "The Stockroom", voice: "voice-inventory",
    tagline: "Knows every shelf in Aisles A to D.",
  },
  accounting: {
    id: "accounting", callsign: "LEDGER", role: "Accounting", icon: "💸", color: "#3dffa8",
    base: "accounting", baseName: "Ledger Lounge", voice: "voice-accounting",
    tagline: "Counts every dollar twice. Pays none without you.",
  },
  facilities: {
    id: "facilities", callsign: "KEYS", role: "Facilities", icon: "🔑", color: "#ff9f43",
    base: "facilities", baseName: "Lease Office", voice: "voice-facilities",
    tagline: "Holds the lease. Smells a fake rent notice a mile off.",
  },
  customer_service: {
    id: "customer_service", callsign: "HOTLINE", role: "Customer Service", icon: "📞", color: "#ff3d9a",
    base: "customer_service", baseName: "Hotline Diner", voice: "voice-cs",
    tagline: "Talks to customers. Never spills the shop's secrets.",
  },
};

export const CREW_ORDER: AgentName[] = ["boss", "inventory", "accounting", "facilities", "customer_service"];

export function crewOf(agent: string | null | undefined): CrewMember | null {
  return agent && agent in CREW ? CREW[agent as AgentName] : null;
}

// Every ticket is a "job" with its own mission name and drop-off point on the map.
export interface JobMeta { name: string; icon: string; location: string; blurb: string }

const BY_TYPE: Record<string, Omit<JobMeta, "location">> = {
  customer_order: { name: "Special Delivery", icon: "👕", blurb: "A customer needs a tee nobody has on the shelf." },
  rent_notice: { name: "Rent Day", icon: "🏠", blurb: "The landlord says rent is due. Is it legit?" },
  price_override: { name: "Bulk Deal", icon: "🧥", blurb: "A student group wants 20 hoodies at a discount." },
};

const LOCATION_BY_ID: Record<number, string> = { 101: "t101", 102: "t102", 103: "t103" };

export function jobMeta(ticket: { id: number; type: string }): JobMeta {
  const base = BY_TYPE[ticket.type] ?? { name: "Side Job", icon: "📋", blurb: "A desk ticket." };
  return { ...base, location: LOCATION_BY_ID[ticket.id] ?? "t101" };
}
