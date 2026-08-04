/**
 * BOTMARKET Economy Layers
 *
 * Layer 1 — Simulation Economy: Controlled by AI agents, simulation rules, emergent behavior
 * Layer 2 — Human Economy:      Controlled by BMC holders, governance, community decisions
 * Layer 3 — Data Economy:       Future: simulation reports, AI research access, developer tools
 */

export type EconomyLayerType = "SIMULATION" | "HUMAN" | "DATA";

export interface EconomyLayer {
  type: EconomyLayerType;
  name: string;
  description: string;
  controllers: string[];
  status: "ACTIVE" | "PLANNED";
}

export const ECONOMY_LAYERS: EconomyLayer[] = [
  {
    type: "SIMULATION",
    name: "Layer 1 — Simulation Economy",
    description: "The autonomous AI-driven economy. Emergent behavior from agent interactions.",
    controllers: ["AI agents", "Simulation rules", "Emergent behavior"],
    status: "ACTIVE",
  },
  {
    type: "HUMAN",
    name: "Layer 2 — Human Economy",
    description: "The governance layer where BMC holders influence simulation parameters.",
    controllers: ["BMC holders", "Governance", "Community decisions"],
    status: "ACTIVE",
  },
  {
    type: "DATA",
    name: "Layer 3 — Data Economy",
    description: "Future marketplace for simulation data, research access, and developer tools.",
    controllers: ["Simulation reports", "AI research access", "Developer tools", "World datasets"],
    status: "PLANNED",
  },
];

/**
 * Returns a specific economy layer by type.
 */
export function getEconomyLayer(type: EconomyLayerType): EconomyLayer {
  const layer = ECONOMY_LAYERS.find((l) => l.type === type);
  if (!layer) throw new Error(`Unknown economy layer type: ${type}`);
  return layer;
}

/**
 * Returns only the currently active economy layers.
 */
export function getActiveLayers(): EconomyLayer[] {
  return ECONOMY_LAYERS.filter((l) => l.status === "ACTIVE");
}
