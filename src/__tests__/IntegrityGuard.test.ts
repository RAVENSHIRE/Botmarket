import { checkProposalIntegrity, isAllowedCategory } from "../simulation/IntegrityGuard";

describe("IntegrityGuard", () => {
  describe("checkProposalIntegrity", () => {
    it("allows valid world-parameter proposals", () => {
      expect(checkProposalIntegrity("Should a new AI civilization region be created?").allowed).toBe(true);
      expect(checkProposalIntegrity("Enable new economic scenario for Asia zone").allowed).toBe(true);
      expect(checkProposalIntegrity("Introduce a new merchant agent archetype").allowed).toBe(true);
      expect(checkProposalIntegrity("Should simulation season 2 restart?").allowed).toBe(true);
    });

    it("blocks proposals containing 'token price'", () => {
      const result = checkProposalIntegrity("Make token price higher for all holders");
      expect(result.allowed).toBe(false);
      expect(result.reason).toContain("token price");
    });

    it("blocks proposals containing 'pump'", () => {
      expect(checkProposalIntegrity("We should pump the token now").allowed).toBe(false);
    });

    it("blocks proposals containing 'give agent'", () => {
      expect(checkProposalIntegrity("Give agent 42 more money to win").allowed).toBe(false);
    });

    it("blocks proposals containing 'drain treasury'", () => {
      expect(checkProposalIntegrity("Drain treasury to reward holders").allowed).toBe(false);
    });

    it("is case-insensitive", () => {
      expect(checkProposalIntegrity("MAKE TOKEN PRICE HIGHER NOW").allowed).toBe(false);
      expect(checkProposalIntegrity("Token Price Should Go Up").allowed).toBe(false);
    });

    it("returns a reason string on failure", () => {
      const result = checkProposalIntegrity("Rug the simulation agents");
      expect(result.allowed).toBe(false);
      expect(typeof result.reason).toBe("string");
      expect(result.reason.length).toBeGreaterThan(0);
    });
  });

  describe("isAllowedCategory", () => {
    it("returns true for all allowed categories", () => {
      expect(isAllowedCategory("WORLD_PARAMETER")).toBe(true);
      expect(isAllowedCategory("NEW_AGENT_ARCHETYPE")).toBe(true);
      expect(isAllowedCategory("ECONOMIC_SCENARIO")).toBe(true);
      expect(isAllowedCategory("SIMULATION_SEASON")).toBe(true);
      expect(isAllowedCategory("REGION_CREATION")).toBe(true);
      expect(isAllowedCategory("EVENT_APPROVAL")).toBe(true);
    });

    it("returns false for disallowed or unknown categories", () => {
      expect(isAllowedCategory("TOKEN_PRICE_MANIPULATION")).toBe(false);
      expect(isAllowedCategory("INDIVIDUAL_AGENT_CONTROL")).toBe(false);
      expect(isAllowedCategory("UNKNOWN")).toBe(false);
      expect(isAllowedCategory("")).toBe(false);
    });
  });
});
