import { getStakingTier, getTierWeightMultiplier, STAKING_TIERS } from "../staking/StakingTiers";

describe("StakingTiers", () => {
  describe("getStakingTier", () => {
    it("returns null for stakes below the minimum tier", () => {
      expect(getStakingTier(0)).toBeNull();
      expect(getStakingTier(999)).toBeNull();
    });

    it("returns Explorer for 1,000 BMC", () => {
      expect(getStakingTier(1_000)?.name).toBe("Explorer");
    });

    it("returns Citizen for 10,000 BMC", () => {
      expect(getStakingTier(10_000)?.name).toBe("Citizen");
    });

    it("returns Architect for 100,000 BMC", () => {
      expect(getStakingTier(100_000)?.name).toBe("Architect");
    });

    it("returns Genesis Council for 1,000,000+ BMC", () => {
      expect(getStakingTier(1_000_000)?.name).toBe("Genesis Council");
      expect(getStakingTier(5_000_000)?.name).toBe("Genesis Council");
    });

    it("returns the highest qualifying tier for an in-between stake", () => {
      // 50,000 qualifies for Citizen (10k) but not Architect (100k)
      expect(getStakingTier(50_000)?.name).toBe("Citizen");
    });

    it("throws on negative stake", () => {
      expect(() => getStakingTier(-1)).toThrow(RangeError);
    });
  });

  describe("getTierWeightMultiplier", () => {
    it("returns correct multipliers for each tier", () => {
      expect(getTierWeightMultiplier("Explorer")).toBe(1);
      expect(getTierWeightMultiplier("Citizen")).toBe(2);
      expect(getTierWeightMultiplier("Architect")).toBe(4);
      expect(getTierWeightMultiplier("Genesis Council")).toBe(8);
    });

    it("returns 0 for unknown tier name", () => {
      expect(getTierWeightMultiplier("Unknown")).toBe(0);
    });
  });

  describe("STAKING_TIERS constant", () => {
    it("has four tiers in ascending order", () => {
      expect(STAKING_TIERS).toHaveLength(4);
      const minValues = STAKING_TIERS.map((t) => t.minBMC);
      expect(minValues).toEqual([...minValues].sort((a, b) => a - b));
    });
  });
});
