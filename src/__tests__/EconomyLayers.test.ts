import { getEconomyLayer, getActiveLayers, ECONOMY_LAYERS } from "../economy/EconomyLayers";

describe("EconomyLayers", () => {
  it("has three layers defined", () => {
    expect(ECONOMY_LAYERS).toHaveLength(3);
  });

  it("Layer 1 is SIMULATION and ACTIVE", () => {
    const layer = getEconomyLayer("SIMULATION");
    expect(layer.type).toBe("SIMULATION");
    expect(layer.status).toBe("ACTIVE");
    expect(layer.controllers).toContain("AI agents");
  });

  it("Layer 2 is HUMAN and ACTIVE", () => {
    const layer = getEconomyLayer("HUMAN");
    expect(layer.type).toBe("HUMAN");
    expect(layer.status).toBe("ACTIVE");
    expect(layer.controllers).toContain("BMC holders");
  });

  it("Layer 3 is DATA and PLANNED", () => {
    const layer = getEconomyLayer("DATA");
    expect(layer.type).toBe("DATA");
    expect(layer.status).toBe("PLANNED");
  });

  it("getActiveLayers returns only ACTIVE layers", () => {
    const active = getActiveLayers();
    expect(active.every((l) => l.status === "ACTIVE")).toBe(true);
    expect(active).toHaveLength(2);
  });

  it("throws for unknown layer type", () => {
    expect(() => getEconomyLayer("UNKNOWN" as any)).toThrow();
  });
});
