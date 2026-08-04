import { createProposal, castVote, tallyVotes, Proposal, Voter } from "../governance/Proposals";

const futureDate = new Date(Date.now() + 86400_000).toISOString();

const validVoter: Voter = {
  id: "user-1",
  stakedBMC: 10_000,
  stakingDays: 90,
  reputationScore: 200,
};

describe("Proposals", () => {
  describe("createProposal", () => {
    it("creates an open proposal for a valid category and description", () => {
      const proposal = createProposal(
        "prop-1",
        "Solar Collapse Simulation",
        "Enable Solar Collapse economic scenario in Zone Alpha",
        "ECONOMIC_SCENARIO",
        futureDate
      );
      expect(proposal.status).toBe("OPEN");
      expect(proposal.votes).toHaveLength(0);
    });

    it("rejects proposals with integrity violations", () => {
      const proposal = createProposal(
        "prop-bad",
        "Price Pump",
        "Make token price higher for all holders",
        "WORLD_PARAMETER",
        futureDate
      );
      expect(proposal.status).toBe("REJECTED_INTEGRITY");
    });

    it("throws for an invalid category", () => {
      expect(() =>
        createProposal("p", "T", "Valid description", "INVALID_CATEGORY", futureDate)
      ).toThrow();
    });
  });

  describe("castVote", () => {
    let openProposal: Proposal;

    beforeEach(() => {
      openProposal = createProposal(
        "prop-2",
        "New Agent Archetype",
        "Introduce a new merchant agent archetype into the simulation",
        "NEW_AGENT_ARCHETYPE",
        futureDate
      );
    });

    it("adds a vote from a staker", () => {
      const updated = castVote(openProposal, validVoter, "YES");
      expect(updated.votes).toHaveLength(1);
      expect(updated.votes[0].voterId).toBe("user-1");
      expect(updated.votes[0].option).toBe("YES");
      expect(updated.votes[0].power).toBeGreaterThan(0);
    });

    it("prevents double voting", () => {
      const afterFirst = castVote(openProposal, validVoter, "YES");
      expect(() => castVote(afterFirst, validVoter, "NO")).toThrow();
    });

    it("throws when voting on a non-OPEN proposal", () => {
      const rejected = createProposal(
        "p-r",
        "Bad",
        "Make token price higher",
        "WORLD_PARAMETER",
        futureDate
      );
      expect(() => castVote(rejected, validVoter, "YES")).toThrow();
    });

    it("allows multiple different voters", () => {
      const voter2: Voter = { id: "user-2", stakedBMC: 100_000, stakingDays: 365, reputationScore: 800 };
      const after1 = castVote(openProposal, validVoter, "YES");
      const after2 = castVote(after1, voter2, "NO");
      expect(after2.votes).toHaveLength(2);
    });
  });

  describe("tallyVotes", () => {
    it("returns NO_VOTES when there are no votes", () => {
      const proposal = createProposal("p-3", "Test", "Enable new region in Zone Beta", "REGION_CREATION", futureDate);
      const result = tallyVotes(proposal);
      expect(result.winner).toBe("NO_VOTES");
      expect(result.totalPower).toBe(0);
    });

    it("correctly identifies the winner by power", () => {
      let proposal = createProposal("p-4", "Test", "Enable new simulation season", "SIMULATION_SEASON", futureDate);

      // Large staker votes YES
      const bigVoter: Voter = { id: "big", stakedBMC: 1_000_000, stakingDays: 365, reputationScore: 1000 };
      // Small staker votes NO
      const smallVoter: Voter = { id: "small", stakedBMC: 1_000, stakingDays: 1, reputationScore: 0 };

      proposal = castVote(proposal, bigVoter, "YES");
      proposal = castVote(proposal, smallVoter, "NO");

      const result = tallyVotes(proposal);
      expect(result.winner).toBe("YES");
      expect(result.breakdown.YES).toBeGreaterThan(result.breakdown.NO);
    });

    it("reports TIE when powers are equal", () => {
      let proposal = createProposal("p-5", "Tie test", "Introduce new archetype X", "NEW_AGENT_ARCHETYPE", futureDate);

      // Identical voters voting different options
      const voterA: Voter = { id: "a", stakedBMC: 10_000, stakingDays: 30, reputationScore: 100 };
      const voterB: Voter = { id: "b", stakedBMC: 10_000, stakingDays: 30, reputationScore: 100 };

      proposal = castVote(proposal, voterA, "YES");
      proposal = castVote(proposal, voterB, "NO");

      const result = tallyVotes(proposal);
      expect(result.winner).toBe("TIE");
    });
  });
});
