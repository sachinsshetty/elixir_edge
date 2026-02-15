# Edge Casualty Tracking System — One-Page Pitch

**Tagline:** *Real-time, off-grid casualty awareness for dismounted operations.*

---

## The Problem

**Command and medics lack a single, reliable picture of who is at risk or down when it matters most.** During long movements, in heat, or when comms are degraded, leaders don’t know who is trending toward heat injury, fatigue, or collapse until it’s too late. Casualties are discovered late, triage is reactive, and preventable losses increase.

---

## Our Approach: Edge-First Casualty Tracking

We turn **wearable vitals + on-device AI** into **structured casualty-risk and alert messages** that flow over **mesh radios** so the right people see the right information—**with or without traditional connectivity**.

| What we do | Why it matters for casualty tracking |
|------------|--------------------------------------|
| **On-device AI** classifies each soldier’s vital summary (HR, SpO₂, activity, sleep) into **Green / Yellow / Red** with a clear recommendation | No cloud, no backend required. Works in denied or degraded comms. |
| **Structured JSON alerts** (person, risk, recommendation, timestamp) are sent over **mesh** (e.g. Meshtastic / T-Echo) | Any receiver (medic tablet, command phone) can parse and display who needs attention, in what order. |
| **Local in-app alert** when risk crosses threshold (Yellow/Red) | The bearer and nearby personnel get an immediate “rest + rehydrate” or “rest in 10 min” prompt even if mesh is down. |
| **Person-tagged reports** (e.g. Soldier 1/2/3 or call signs) | Every alert is tied to an identity so command and medics know **who** is at risk, not just that “someone” is. |

---

## How It Fits the “Human Readiness” Idea

The challenge describes a **“human readiness” layer** alongside equipment readiness: *who is trending toward failure, and why.* Our system delivers exactly that for **people**:

- **Input:** Vitals-style text (or future BLE from wearables): e.g. *“HR average 88 bpm HR max 105 SpO2 95 percent steps 5000 active 25 minutes sleep 4h.”*
- **Output:** A **risk level** (Green/Yellow/Red), a **recommendation** (e.g. “Monitor vital signs…” or “Heat stress risk. Rest and rehydrate. Recommend rest in 10 min.”), and an **alert flag** when threshold is crossed.
- **Distribution:** One-hop or multi-hop **mesh** so squad leaders and medics get the same structured feed for casualty tracking and triage ordering—even when comms are degraded.

---

## Operational Picture (Casualty Tracking)

1. **Each soldier** (or a designated reporter) enters or streams vitals into a phone/hub running the app; the **edge model** classifies risk and recommendation.
2. **When risk is Yellow or Red**, the device shows a **local alert** and sends a **structured message** on the mesh: person ID, risk, recommendation, timestamp, `alert: true`.
3. **Command / medic** devices receive these messages and can maintain a **casualty-risk list**: who is Red, who is Yellow, who was last seen Green—with timestamps and recommendations.
4. **When comms return**, the same structured events can sync to a backend for **after-action review** and trend analysis (future phase).

No dependency on cell or tactical net for the core loop; mesh + edge do the work.

---

## What We’ve Built (Current Scope)

- **Android app** with on-device AI (health text → Green/Yellow/Red + recommendation).
- **Structured JSON payload** over mesh: `person`, `ts`, `risk`, `analysis` (recommendation), `alert`, `input`.
- **Threshold-based local alert** (dialog) when risk is Yellow or Red.
- **Person selector** (e.g. 3 personnel) so every report is attributed.
- **One-way send** to mesh (e.g. LilyGo T-Echo / Meshtastic) for reliability and simplicity; receive/squad view is a natural next step for a full casualty tracking dashboard.

---

## Ask / Next Step

We are solving **casualty tracking at the edge**: **who is at risk, with what recommendation, over mesh, without relying on the cloud or intact comms.**  

**Next steps we propose:**  
- Pilot with a single squad/platoon: vitals in → structured alerts out → one command/medic device receiving and displaying a **casualty-risk list**.  
- Extend to **receive + simple squad view** (e.g. Green/Yellow/Red by person) and optional **backend sync** when connectivity returns.

---

*Edge Soldier Health Monitoring (AI-Enabled Wearable Sensing) — casualty tracking, first.*
