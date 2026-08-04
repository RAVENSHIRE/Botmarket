/**
 * BOTMARKET Human Roles
 *
 * Defines the three roles humans can have in the BOTMARKET ecosystem:
 *   1. Observer   — no token required, read-only access
 *   2. BMC Holder — holds BMC, community governance access
 *   3. BMC Staker — locks BMC, full governance + reputation + rewards
 */

import { getStakingTier, StakingTier } from "../staking/StakingTiers";
import { calculateVotingPower, VotingPowerBreakdown } from "../governance/VotingPower";

export type RoleType = "OBSERVER" | "BMC_HOLDER" | "BMC_STAKER";

export interface RoleCapabilities {
  canViewGlobe: boolean;
  canReadAgentConversations: boolean;
  canAccessAdvancedData: boolean;
  canVoteGovernance: boolean;
  canStake: boolean;
  canEarnRewards: boolean;
}

export const ROLE_CAPABILITIES: Record<RoleType, RoleCapabilities> = {
  OBSERVER: {
    canViewGlobe: true,
    canReadAgentConversations: true,
    canAccessAdvancedData: false,
    canVoteGovernance: false,
    canStake: false,
    canEarnRewards: false,
  },
  BMC_HOLDER: {
    canViewGlobe: true,
    canReadAgentConversations: true,
    canAccessAdvancedData: true,
    canVoteGovernance: true,
    canStake: false,
    canEarnRewards: false,
  },
  BMC_STAKER: {
    canViewGlobe: true,
    canReadAgentConversations: true,
    canAccessAdvancedData: true,
    canVoteGovernance: true,
    canStake: true,
    canEarnRewards: true,
  },
};

export interface HumanParticipant {
  id: string;
  role: RoleType;
  bmcBalance: number;
  stakedBMC: number;
  stakingDays: number;
  reputationScore: number;
}

/**
 * Derives the effective role for a participant based on their current
 * token balances and staking position.
 */
export function deriveRole(participant: Pick<HumanParticipant, "bmcBalance" | "stakedBMC">): RoleType {
  if (participant.stakedBMC > 0) return "BMC_STAKER";
  if (participant.bmcBalance > 0) return "BMC_HOLDER";
  return "OBSERVER";
}

/**
 * Returns the staking tier for a participant, if they are staking.
 */
export function getParticipantTier(participant: HumanParticipant): StakingTier | null {
  if (participant.stakedBMC <= 0) return null;
  return getStakingTier(participant.stakedBMC);
}

/**
 * Returns the full voting power breakdown for a staker.
 * Returns null for non-stakers (Observers and BMC Holders with no stake).
 */
export function getParticipantVotingPower(participant: HumanParticipant): VotingPowerBreakdown | null {
  if (participant.stakedBMC <= 0) return null;
  return calculateVotingPower({
    stakedBMC: participant.stakedBMC,
    stakingDays: participant.stakingDays,
    reputationScore: participant.reputationScore,
  });
}

/**
 * Returns the capabilities for a given role.
 */
export function getRoleCapabilities(role: RoleType): RoleCapabilities {
  return ROLE_CAPABILITIES[role];
}
