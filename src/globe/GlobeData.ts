/**
 * BOTMARKET 3D Globe Data API
 *
 * Provides structured data for the globe experience.
 * Users can zoom into regions, watch agent societies evolve,
 * view economic activity, and see historical timelines.
 */

export interface AgentZone {
  id: string;
  name: string;
  agentCount: number;
  /** GeoJSON-style coordinates [longitude, latitude] */
  coordinates: [number, number];
  tradeVolume: number;
  politicalAlliances: string[];
  economicTrend: "GROWING" | "STABLE" | "DECLINING";
  historicalEvents: HistoricalEvent[];
}

export interface HistoricalEvent {
  timestamp: string;
  type: "ALLIANCE_FORMED" | "TRADE_AGREEMENT" | "CONFLICT" | "MIGRATION" | "ECONOMIC_SHIFT";
  description: string;
  agentsInvolved: number;
}

export interface GlobeSnapshot {
  capturedAt: string;
  totalAgents: number;
  zones: AgentZone[];
}

/**
 * Returns a summary of all active zones for globe rendering.
 */
export function getGlobeSummary(snapshot: GlobeSnapshot): {
  capturedAt: string;
  totalAgents: number;
  zoneCount: number;
  zoneNames: string[];
} {
  return {
    capturedAt: snapshot.capturedAt,
    totalAgents: snapshot.totalAgents,
    zoneCount: snapshot.zones.length,
    zoneNames: snapshot.zones.map((z) => z.name),
  };
}

/**
 * Filters zones by economic trend for targeted monitoring.
 */
export function getZonesByTrend(
  snapshot: GlobeSnapshot,
  trend: AgentZone["economicTrend"]
): AgentZone[] {
  return snapshot.zones.filter((z) => z.economicTrend === trend);
}

/**
 * Returns the most recent historical events across all zones,
 * sorted by timestamp descending.
 */
export function getRecentEvents(snapshot: GlobeSnapshot, limit = 10): HistoricalEvent[] {
  const events: HistoricalEvent[] = snapshot.zones.flatMap((z) => z.historicalEvents);
  events.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  return events.slice(0, limit);
}
