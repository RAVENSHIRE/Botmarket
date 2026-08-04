/**
 * BOTMARKET Simulation Integrity Guard
 *
 * Ensures humans can only vote on simulation-level parameters,
 * never on token price or individual agent decisions.
 *
 * ✅ Allowed: "Enable new economic scenario", "Introduce new agent species",
 *            "Change simulation rules", "Create new region"
 * ❌ Blocked: "Make token price higher", "Give agent X more money", etc.
 */

/** Categories of proposals humans are allowed to vote on */
export type AllowedProposalCategory =
  | "WORLD_PARAMETER"
  | "NEW_AGENT_ARCHETYPE"
  | "ECONOMIC_SCENARIO"
  | "SIMULATION_SEASON"
  | "REGION_CREATION"
  | "EVENT_APPROVAL";

/** Categories of proposals that are explicitly forbidden */
export type ForbiddenProposalCategory =
  | "TOKEN_PRICE_MANIPULATION"
  | "INDIVIDUAL_AGENT_CONTROL"
  | "TREASURY_DRAIN";

const FORBIDDEN_KEYWORDS: string[] = [
  "token price",
  "price higher",
  "price lower",
  "pump",
  "moon",
  "make price",
  "agent wallet",
  "agent balance",
  "give agent",
  "agent money",
  "treasury withdraw",
  "drain treasury",
  "rug",
];

export interface ProposalGuardResult {
  allowed: boolean;
  reason: string;
}

/**
 * Checks whether a proposal text passes the simulation integrity guard.
 * Returns { allowed: false, reason } if the proposal violates integrity rules.
 */
export function checkProposalIntegrity(proposalText: string): ProposalGuardResult {
  const lower = proposalText.toLowerCase();

  for (const keyword of FORBIDDEN_KEYWORDS) {
    if (lower.includes(keyword)) {
      return {
        allowed: false,
        reason: `Proposal violates simulation integrity: contains forbidden phrase "${keyword}". Humans may only vote on world parameters, not token economics or individual agent decisions.`,
      };
    }
  }

  return { allowed: true, reason: "Proposal passes integrity check." };
}

/**
 * Returns true if a given category is a valid, allowed proposal category.
 */
export function isAllowedCategory(category: string): category is AllowedProposalCategory {
  const allowed: AllowedProposalCategory[] = [
    "WORLD_PARAMETER",
    "NEW_AGENT_ARCHETYPE",
    "ECONOMIC_SCENARIO",
    "SIMULATION_SEASON",
    "REGION_CREATION",
    "EVENT_APPROVAL",
  ];
  return allowed.includes(category as AllowedProposalCategory);
}
