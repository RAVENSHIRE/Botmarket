/**
 * BOTMARKET Governance Proposal & Voting System
 *
 * Humans vote on world parameters and simulation events.
 * Each vote is weighted by the voter's calculated voting power.
 */

import { calculateVotingPower, VotingPowerInput } from "./VotingPower";
import { checkProposalIntegrity, isAllowedCategory, AllowedProposalCategory } from "../simulation/IntegrityGuard";

export type VoteOption = "YES" | "NO" | "MODIFY";

export interface Voter extends VotingPowerInput {
  id: string;
}

export interface Vote {
  voterId: string;
  option: VoteOption;
  /** Weighted power of this vote */
  power: number;
}

export interface Proposal {
  id: string;
  title: string;
  description: string;
  category: AllowedProposalCategory;
  /** ISO 8601 timestamp */
  createdAt: string;
  /** ISO 8601 timestamp when voting closes */
  closesAt: string;
  votes: Vote[];
  status: "OPEN" | "CLOSED" | "REJECTED_INTEGRITY";
}

export interface VoteResult {
  proposalId: string;
  title: string;
  totalPower: number;
  breakdown: Record<VoteOption, number>;
  winner: VoteOption | "TIE" | "NO_VOTES";
}

/**
 * Creates a new governance proposal after passing integrity checks.
 * Throws if the proposal violates simulation integrity rules.
 */
export function createProposal(
  id: string,
  title: string,
  description: string,
  category: string,
  closesAt: string
): Proposal {
  if (!isAllowedCategory(category)) {
    throw new Error(`Invalid proposal category: "${category}". Must be one of the allowed categories.`);
  }

  const integrityCheck = checkProposalIntegrity(description);
  if (!integrityCheck.allowed) {
    return {
      id,
      title,
      description,
      category: category as AllowedProposalCategory,
      createdAt: new Date().toISOString(),
      closesAt,
      votes: [],
      status: "REJECTED_INTEGRITY",
    };
  }

  return {
    id,
    title,
    description,
    category: category as AllowedProposalCategory,
    createdAt: new Date().toISOString(),
    closesAt,
    votes: [],
    status: "OPEN",
  };
}

/**
 * Casts a vote on an open proposal.
 * Voting power is calculated from the voter's staking and reputation data.
 * Throws if the proposal is not OPEN or if the voter has already voted.
 */
export function castVote(proposal: Proposal, voter: Voter, option: VoteOption): Proposal {
  if (proposal.status !== "OPEN") {
    throw new Error(`Cannot vote on proposal "${proposal.id}": status is ${proposal.status}`);
  }

  const alreadyVoted = proposal.votes.some((v) => v.voterId === voter.id);
  if (alreadyVoted) {
    throw new Error(`Voter "${voter.id}" has already voted on proposal "${proposal.id}"`);
  }

  const powerBreakdown = calculateVotingPower(voter);

  const vote: Vote = {
    voterId: voter.id,
    option,
    power: powerBreakdown.total,
  };

  return {
    ...proposal,
    votes: [...proposal.votes, vote],
  };
}

/**
 * Tallies votes for a proposal and returns the result.
 */
export function tallyVotes(proposal: Proposal): VoteResult {
  const breakdown: Record<VoteOption, number> = { YES: 0, NO: 0, MODIFY: 0 };
  let totalPower = 0;

  for (const vote of proposal.votes) {
    breakdown[vote.option] += vote.power;
    totalPower += vote.power;
  }

  if (totalPower === 0) {
    return {
      proposalId: proposal.id,
      title: proposal.title,
      totalPower: 0,
      breakdown,
      winner: "NO_VOTES",
    };
  }

  const entries = Object.entries(breakdown) as [VoteOption, number][];
  const maxPower = Math.max(...entries.map(([, p]) => p));
  const winners = entries.filter(([, p]) => p === maxPower).map(([opt]) => opt);

  const winner: VoteOption | "TIE" = winners.length === 1 ? winners[0] : "TIE";

  return {
    proposalId: proposal.id,
    title: proposal.title,
    totalPower: parseFloat(totalPower.toFixed(4)),
    breakdown: {
      YES: parseFloat(breakdown.YES.toFixed(4)),
      NO: parseFloat(breakdown.NO.toFixed(4)),
      MODIFY: parseFloat(breakdown.MODIFY.toFixed(4)),
    },
    winner,
  };
}
