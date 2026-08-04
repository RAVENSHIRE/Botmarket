import { deriveRole, getParticipantTier, getParticipantVotingPower, getRoleCapabilities, HumanParticipant } from "../roles/HumanRoles";

const baseParticipant: HumanParticipant = {
  id: "p-1",
  role: "OBSERVER",
  bmcBalance: 0,
  stakedBMC: 0,
  stakingDays: 0,
  reputationScore: 0,
};

describe("HumanRoles", () => {
  describe("deriveRole", () => {
    it("returns OBSERVER when no BMC held or staked", () => {
      expect(deriveRole({ bmcBalance: 0, stakedBMC: 0 })).toBe("OBSERVER");
    });

    it("returns BMC_HOLDER when BMC held but not staked", () => {
      expect(deriveRole({ bmcBalance: 500, stakedBMC: 0 })).toBe("BMC_HOLDER");
    });

    it("returns BMC_STAKER when BMC is staked", () => {
      expect(deriveRole({ bmcBalance: 0, stakedBMC: 10_000 })).toBe("BMC_STAKER");
    });

    it("returns BMC_STAKER even if balance is also held", () => {
      expect(deriveRole({ bmcBalance: 1000, stakedBMC: 5_000 })).toBe("BMC_STAKER");
    });
  });

  describe("getParticipantTier", () => {
    it("returns null for non-stakers", () => {
      expect(getParticipantTier({ ...baseParticipant, stakedBMC: 0 })).toBeNull();
    });

    it("returns Explorer for 1,000 staked", () => {
      expect(getParticipantTier({ ...baseParticipant, stakedBMC: 1_000 })?.name).toBe("Explorer");
    });

    it("returns Genesis Council for 1M staked", () => {
      expect(getParticipantTier({ ...baseParticipant, stakedBMC: 1_000_000 })?.name).toBe("Genesis Council");
    });
  });

  describe("getParticipantVotingPower", () => {
    it("returns null for non-stakers", () => {
      expect(getParticipantVotingPower(baseParticipant)).toBeNull();
    });

    it("returns a breakdown for stakers", () => {
      const staker: HumanParticipant = { ...baseParticipant, stakedBMC: 10_000, stakingDays: 60, reputationScore: 300 };
      const power = getParticipantVotingPower(staker);
      expect(power).not.toBeNull();
      expect(power!.total).toBeGreaterThan(0);
    });
  });

  describe("getRoleCapabilities", () => {
    it("OBSERVER cannot vote or earn rewards", () => {
      const caps = getRoleCapabilities("OBSERVER");
      expect(caps.canViewGlobe).toBe(true);
      expect(caps.canVoteGovernance).toBe(false);
      expect(caps.canEarnRewards).toBe(false);
    });

    it("BMC_HOLDER can vote but not earn rewards", () => {
      const caps = getRoleCapabilities("BMC_HOLDER");
      expect(caps.canVoteGovernance).toBe(true);
      expect(caps.canEarnRewards).toBe(false);
    });

    it("BMC_STAKER has full capabilities", () => {
      const caps = getRoleCapabilities("BMC_STAKER");
      expect(caps.canVoteGovernance).toBe(true);
      expect(caps.canStake).toBe(true);
      expect(caps.canEarnRewards).toBe(true);
    });
  });
});
