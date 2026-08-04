/**
 * BOTMARKET Governance Voting Power
 *
 * Hybrid model to avoid pure whale control.
 *
 * Voting Power = Stake Weight + Participation Reputation + Time Commitment
 */

import { getStakingTier, getTierWeightMultiplier } from "../staking/StakingTiers";

export interface VotingPowerInput {
  /** Amount of BMC currently staked */
  stakedBMC: number;
  /**
   * Duration in days the user has been staking continuously.
   * Longer commitment is rewarded with a time bonus.
   */
  stakingDays: number;
  /**
   * Reputation score earned via governance participation and community
   * contributions. Ranges from 0 to 1000.
   */
  reputationScore: number;
}

export interface VotingPowerBreakdown {
  stakeWeight: number;
  timeCommitment: number;
  participationReputation: number;
  total: number;
}

/**
 * Calculates the composite voting power for a user.
 *
 * Formula:
 *   stakeWeight         = log10(stakedBMC + 1) * tierMultiplier
 *   timeCommitment      = sqrt(stakingDays) * 0.5
 *   participationRep    = reputationScore * 0.1
 *   total               = stakeWeight + timeCommitment + participationRep
 *
 * Using logarithmic scaling for BMC prevents whales from having
 * unbounded dominance while still rewarding larger stakes.
 */
export function calculateVotingPower(input: VotingPowerInput): VotingPowerBreakdown {
  const { stakedBMC, stakingDays, reputationScore } = input;

  if (stakedBMC < 0) throw new RangeError("stakedBMC cannot be negative");
  if (stakingDays < 0) throw new RangeError("stakingDays cannot be negative");
  if (reputationScore < 0 || reputationScore > 1000) {
    throw new RangeError("reputationScore must be between 0 and 1000");
  }

  const tier = getStakingTier(stakedBMC);
  const tierMultiplier = tier ? getTierWeightMultiplier(tier.name) : 0;

  const stakeWeight = Math.log10(stakedBMC + 1) * tierMultiplier;
  const timeCommitment = Math.sqrt(stakingDays) * 0.5;
  const participationReputation = reputationScore * 0.1;

  const total = stakeWeight + timeCommitment + participationReputation;

  return {
    stakeWeight: parseFloat(stakeWeight.toFixed(4)),
    timeCommitment: parseFloat(timeCommitment.toFixed(4)),
    participationReputation: parseFloat(participationReputation.toFixed(4)),
    total: parseFloat(total.toFixed(4)),
  };
}
