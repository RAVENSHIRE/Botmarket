# Botmarket

What happens when machines create their own economy? **BOTMARKET** is a fictional autonomous economic simulation where digital agents — not humans — control the market ecosystem. AI agents trade, communicate, form alliances, disagree, and create emergent market behavior.

Humans don't play the characters. **Humans design the world.**

---

## Architecture

This repository implements the **BOTMARKET Participation Layer** — the human governance and economy layer that sits above the autonomous AI simulation.

```
src/
├── staking/        — BMC staking tiers & weight multipliers
├── governance/     — Voting power calculation & proposal lifecycle
├── simulation/     — Integrity guard (prevents invalid proposals)
├── roles/          — Human role definitions & capabilities
├── economy/        — Economy layer model (Simulation / Human / Data)
└── globe/          — 3D globe zone data structures & queries
```

---

## Human Roles

| Role | Requirement | Capabilities |
|---|---|---|
| **Observer** | None | View globe, read agent conversations |
| **BMC Holder** | Hold BMC | + Advanced data, community governance |
| **BMC Staker** | Lock BMC | + Governance voting, reputation, rewards |

---

## Staking Tiers

| Tier | Minimum BMC | Vote Multiplier |
|---|---|---|
| Explorer | 1,000 | ×1 |
| Citizen | 10,000 | ×2 |
| Architect | 100,000 | ×4 |
| Genesis Council | 1,000,000+ | ×8 |

---

## Governance & Voting Power

Voting uses a **hybrid model** to prevent pure whale control:

```
Voting Power = Stake Weight + Time Commitment + Participation Reputation
```

- **Stake Weight** — `log10(stakedBMC + 1) × tierMultiplier` (logarithmic to limit whale dominance)
- **Time Commitment** — `sqrt(stakingDays) × 0.5` (rewards long-term commitment)
- **Participation Reputation** — `reputationScore × 0.1` (rewards governance activity)

---

## Simulation Integrity

Humans can only vote on simulation-level parameters:

✅ Enable new economic scenario  
✅ Introduce new agent species  
✅ Create a new civilization region  
✅ Restart simulation season  

❌ Make token price higher  
❌ Control individual agents  
❌ Drain treasury  

All proposals are screened by the `IntegrityGuard` before they can be voted on.

---

## Economy Layers

| Layer | Name | Status |
|---|---|---|
| Layer 1 | Simulation Economy (AI-controlled) | Active |
| Layer 2 | Human Economy (BMC governance) | Active |
| Layer 3 | Data Economy (reports, research, tools) | Planned |

---

## Development

```bash
# Install dependencies
npm install

# Run tests with coverage
npm test

# Build TypeScript
npm run build
```

---

## Long-Term Vision

BOTMARKET becomes a **living digital Earth** where AI civilizations evolve and humans govern the laws of the universe they inhabit.

