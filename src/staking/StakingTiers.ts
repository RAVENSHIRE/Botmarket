/**
 * BOTMARKET Staking Tiers
 *
 * Users lock BMC to become ecosystem supporters.
 * Higher stakes unlock greater governance weight, reputation, and access tiers.
 */

export interface StakingTier {
  name: string;
  minBMC: number;
  description: string;
}

export const STAKING_TIERS: StakingTier[] = [
  { name: "Explorer", minBMC: 1_000, description: "Entry-level ecosystem supporter" },
  { name: "Citizen", minBMC: 10_000, description: "Active community participant" },
  { name: "Architect", minBMC: 100_000, description: "World-builder and senior contributor" },
  { name: "Genesis Council", minBMC: 1_000_000, description: "Founding council member with maximum influence" },
];

/**
 * Returns the highest staking tier a user qualifies for based on their BMC stake.
 * Returns null if the stake is below the minimum for any tier.
 */
export function getStakingTier(stakedBMC: number): StakingTier | null {
  if (stakedBMC < 0) {
    throw new RangeError("stakedBMC cannot be negative");
  }
  const qualified = STAKING_TIERS.filter((t) => stakedBMC >= t.minBMC);
  if (qualified.length === 0) return null;
  return qualified[qualified.length - 1];
}

/**
 * Returns the staking weight multiplier for a given tier name.
 * Used as a component of voting power calculation.
 */
export function getTierWeightMultiplier(tierName: string): number {
  const multipliers: Record<string, number> = {
    Explorer: 1,
    Citizen: 2,
    Architect: 4,
    "Genesis Council": 8,
  };
  return multipliers[tierName] ?? 0;
}
