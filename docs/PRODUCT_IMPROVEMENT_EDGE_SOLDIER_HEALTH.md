# Edge Soldier Health Monitoring – Product Improvement Plan

**Challenge:** Edge Soldier Health Monitoring (AI-Enabled Wearable Sensing)  
**Current product:** Elixir T-Echo app – health text input → on-device AI classification → one-way mesh broadcast (Person + Health + Level).

---

## 1. Gap vs. Challenge (Summary)

| Challenge need | Current state | Priority |
|----------------|---------------|----------|
| Structured vital signs (HR, temp, SpO₂, etc.) | Free-text health input only | **High** |
| Wearable / ambient sensor input | None | **High** |
| Real-time risk thresholds & alerts | Single classification, no thresholds or alerts | **High** |
| “Heat stress probability” + time-to-action | Generic AI level only | **High** |
| Squad status map (green/yellow/red) | No status view | **High** |
| Medic triage-ranked view | No triage or ranking | **Medium** |
| Works when comms degraded | Mesh + local edge fits; no explicit “offline first” design | **Medium** |
| Backend sync when comms return | No sync or summarization | **Later** |

---

## 2. Recommended Improvements (Prioritized)

### Phase 1 – Structured data & risk (foundation)

**1.1 Structured health payload (not free text)**  
- **Why:** Command/medics need machine-readable vitals and risk, not prose.  
- **What:** Define a small, fixed schema for “soldier health report” and send that on the mesh (e.g. JSON or compact key-value).  
- **Example fields:**  
  - `person_id` (or name), `timestamp`  
  - `hr`, `hrv`, `skin_temp`, `spo2` (if available), `activity` (from accelerometer if you add it later)  
  - `ambient_temp`, `wbgt` or `humidity` (if available)  
  - `risk_level`: green / yellow / red  
  - `heat_stress_probability` (0–1) or equivalent from your AI  
  - `recommendation`: e.g. “rest + hydration in 10 min”  
- **How in app:**  
  - Replace or complement free-text input with structured fields (e.g. number inputs for HR, temp, SpO₂; dropdown for risk if no AI yet).  
  - Keep “Person” dropdown; add “Report type” (e.g. manual / from wearable) if useful.  
  - Build one string (e.g. JSON) from these fields and send that as the mesh message so any receiver (medic app, backend) can parse it.

**1.2 Edge AI aligned to heat strain / fatigue**  
- **Why:** Challenge asks for “heat strain and fatigue trends” and “heat stress probability.”  
- **What:**  
  - Train or fine-tune the on-device model to output: (1) risk level (green/yellow/red), (2) heat-stress probability (0–1), (3) short recommendation (e.g. “rest + hydration in 10 min”).  
  - Inputs: vitals (HR, HRV, skin temp, SpO₂ if used) + optional ambient (WBGT/temp/humidity).  
- **How in app:**  
  - Pass structured vitals (and env) into the classifier; map model output to the structured payload above (risk_level, heat_stress_probability, recommendation).  
  - Display the same in the app (e.g. “Heat stress: 0.82 – Rest + hydration in 10 min”) and include in the mesh message.

**1.3 Local alerts when risk crosses threshold**  
- **Why:** “When risk crosses threshold, the system generates an alert” even without connectivity.  
- **What:**  
  - In the app, compare AI output (e.g. heat_stress_probability or risk_level) to configurable thresholds (e.g. yellow > 0.5, red > 0.8).  
  - On crossing threshold: show an in-app alert (and optionally vibration/sound); optionally send a dedicated “alert” message on the mesh (same structured format with `alert: true` and priority).  
- **How:**  
  - After each classification, if probability or level exceeds threshold → trigger AlertDialog / notification and, if connected, one “alert” mesh message so medic/squad view can prioritize it.

---

### Phase 2 – Visibility for command & medic

**2.1 Squad status map (green/yellow/red)**  
- **Why:** “Squad leader sees a simple status map (green/yellow/red).”  
- **What:**  
  - A second screen (or second app/tablet role): “Squad view” that only receives and displays.  
  - List or grid of soldiers (Person 1, 2, 3 or IDs); each has last reported risk level and optional last timestamp.  
  - Color coding: green / yellow / red from `risk_level` (or from heat_stress_probability bands).  
- **How:**  
  - Re-enable receive on the T-Echo (PROTO or TEXTMSG as you did before); parse incoming structured messages; maintain a small in-memory “last status per person”; UI shows one row/card per person with color and last update time.  
  - Can be same app with a “Squad view” tab/mode, or a separate “command/medic” build that only receives and displays.

**2.2 Triage-ranked medic view**  
- **Why:** “Medic receives triage-ranked alerts even without connectivity.”  
- **What:**  
  - In the squad/medic view, sort or filter by risk (red first, then yellow, then green) and optionally by time (e.g. “recommend rest in 10 min” → sort by urgency).  
  - Mark which messages are “alerts” (threshold crossed) vs. routine updates.  
- **How:**  
  - Store last N messages per person; sort by risk_level (red > yellow > green) and by `heat_stress_probability` descending; show “Alert” badge when `alert: true`.  
  - All data can come from mesh only (no backend) so it works when comms are degraded.

---

### Phase 3 – Sensors & environmental (when hardware exists)

**3.1 Wearable sensor input**  
- **Why:** Challenge assumes “wearable sensors (HR/HRV, skin temp, SpO₂, accelerometer)”.  
- **What:**  
  - When hardware is available: ingest vitals from BLE wearables or a rugged hub that aggregates sensors.  
  - App: either “manual entry” (current) or “from wearable” (numeric fields auto-filled from BLE); same structured payload and same mesh message format.  
- **How:**  
  - Add BLE scanning/connection to a known device or GATT profile; read characteristics for HR, temp, SpO₂, etc.; map to your structured fields and feed the same pipeline (AI → threshold → send).

**3.2 Ambient (WBGT / temp / humidity)**  
- **Why:** “Ambient sensors (WBGT/temperature/humidity)” improve heat-stress accuracy.  
- **What:**  
  - If the T-Echo or another device exposes ambient readings, send them in the same report (e.g. `ambient_temp`, `wbgt`, `humidity`).  
  - Use as extra inputs to the edge model for heat-stress probability.  
- **How:**  
  - One optional “environment” block in the structured message; model input vector includes these when present.

---

### Phase 4 – Resilience & backend (later)

**4.1 Offline-first and queue**  
- **Why:** “When comms are degraded” – mesh may be intermittent.  
- **What:**  
  - Queue outgoing reports locally; when T-Echo is connected, send oldest first; mark “sent” when ack’d or after timeout.  
  - Alerts still trigger locally (in-app) even if mesh send fails.  
- **How:**  
  - Simple SQLite or file-based queue; on connect, drain queue; retry with backoff.

**4.2 Backend sync when comms return**  
- **Why:** “Summarized events sync to the backend for trend analysis and after-action review.”  
- **What:**  
  - When network is available, upload batched “events” (timestamp, person, vitals, risk, alert flag) to a server; no need for real-time cloud during the op.  
- **How:**  
  - Optional “Sync” button or background job when WiFi/cellular is available; POST to REST API; clear local batch after success.

---

## 3. Message Format Suggestion (Structured)

Use a single, compact format for both “routine report” and “alert” so squad view and medic view can parse the same way. Example (JSON):

```json
{
  "v": 1,
  "person": "Person 1",
  "ts": 1699876543,
  "hr": 92,
  "skin_temp": 37.2,
  "spo2": 98,
  "ambient_temp": 34,
  "risk": "yellow",
  "heat_stress_p": 0.82,
  "rec": "rest + hydration in 10 min",
  "alert": true
}
```

- **v:** schema version.  
- **person / ts:** who and when.  
- **hr, skin_temp, spo2, ambient_temp:** optional; use null if not available.  
- **risk:** green | yellow | red.  
- **heat_stress_p:** 0–1.  
- **rec:** short recommendation from AI.  
- **alert:** true if this send was due to threshold cross.

Send this as the mesh text payload (one JSON object per message). Receivers (squad/medic view) parse and update status map / triage list.

---

## 4. Quick Wins in the Current App (No new hardware)

1. **Structured message:** Add numeric fields (HR, temp, SpO₂) and risk dropdown; build JSON (or CSV) and send that instead of free text.  
2. **Threshold + local alert:** From current AI output, derive a simple “risk” (e.g. from confidence or label); if above threshold, show AlertDialog and optionally send one “alert” message.  
3. **Squad view in same app:** Re-enable receive; parse structured messages; new tab “Squad” with 3 rows (Person 1/2/3), color by last risk, last-update time.  
4. **Person names:** Rename “Person 1/2/3” to soldier IDs or call signs in the dropdown and in the message schema.

---

## 5. One-Line Roadmap

**Now:** Structured payload (vitals + risk + recommendation) + local threshold alerts.  
**Next:** Squad view (green/yellow/red) + triage-ranked medic list from mesh.  
**Then:** BLE wearable + ambient inputs when hardware exists; backend sync when comms return.

This keeps the product aligned with the challenge (edge, mesh, human readiness, medic triage) and improves it step by step without depending on new hardware first.
