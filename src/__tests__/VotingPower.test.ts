import { calculateVotingPower } from "../governance/VotingPower";

describe("VotingPower", () => {
  describe("calculateVotingPower", () => {
    it("returns zero total power for an unstaked user", () => {
      const result = calculateVotingPower({
        stakedBMC: 0,
        stakingDays: 0,
        reputationScore: 0,
      });
      expect(result.stakeWeight).toBe(0);
      expect(result.total).toBe(0);
    });

    it("increases voting power with higher stake", () => {
      const low = calculateVotingPower({ stakedBMC: 1_000, stakingDays: 30, reputationScore: 100 });
      const high = calculateVotingPower({ stakedBMC: 1_000_000, stakingDays: 30, reputationScore: 100 });
      expect(high.total).toBeGreaterThan(low.total);
    });

    it("increases voting power with longer staking duration", () => {
      const short = calculateVotingPower({ stakedBMC: 10_000, stakingDays: 10, reputationScore: 200 });
      const long = calculateVotingPower({ stakedBMC: 10_000, stakingDays: 365, reputationScore: 200 });
      expect(long.timeCommitment).toBeGreaterThan(short.timeCommitment);
      expect(long.total).toBeGreaterThan(short.total);
    });

    it("increases voting power with higher reputation", () => {
      const lowRep = calculateVotingPower({ stakedBMC: 10_000, stakingDays: 60, reputationScore: 0 });
      const highRep = calculateVotingPower({ stakedBMC: 10_000, stakingDays: 60, reputationScore: 1000 });
      expect(highRep.participationReputation).toBeGreaterThan(lowRep.participationReputation);
    });

    it("uses logarithmic scaling — doubling stake does not double stake weight", () => {
      const base = calculateVotingPower({ stakedBMC: 10_000, stakingDays: 0, reputationScore: 0 });
      const doubled = calculateVotingPower({ stakedBMC: 20_000, stakingDays: 0, reputationScore: 0 });
      // Doubled stake should result in less than double the stake weight
      expect(doubled.stakeWeight).toBeLessThan(base.stakeWeight * 2);
    });

    it("throws on negative stakedBMC", () => {
      expect(() => calculateVotingPower({ stakedBMC: -1, stakingDays: 0, reputationScore: 0 })).toThrow(RangeError);
    });

    it("throws on negative stakingDays", () => {
      expect(() => calculateVotingPower({ stakedBMC: 1000, stakingDays: -1, reputationScore: 0 })).toThrow(RangeError);
    });

    it("throws when reputationScore exceeds 1000", () => {
      expect(() => calculateVotingPower({ stakedBMC: 1000, stakingDays: 0, reputationScore: 1001 })).toThrow(RangeError);
    });

    it("returns a breakdown with four fields all >= 0", () => {
      const result = calculateVotingPower({ stakedBMC: 10_000, stakingDays: 30, reputationScore: 500 });
      expect(result.stakeWeight).toBeGreaterThanOrEqual(0);
      expect(result.timeCommitment).toBeGreaterThanOrEqual(0);
      expect(result.participationReputation).toBeGreaterThanOrEqual(0);
      expect(result.total).toBeCloseTo(
        result.stakeWeight + result.timeCommitment + result.participationReputation,
        2
      );
    });
  });
});
