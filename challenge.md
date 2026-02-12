Challenge

- Title
    - Edge Soldier Health Monitoring (AI-Enabled Wearable Sensing)	
- Problem Statement
    - Command and medics lack timely, reliable visibility into individual soldier health status (heat stress, dehydration, fatigue, injury risk). This leads to preventable casualties, reduced operational tempo, and delayed triage—especially when comms are degraded or medics are overloaded.
- Context
    - Wearable sensors + edge AI can continuously monitor vital signs and environmental exposure, producing real-time risk alerts locally (no cloud dependency). Data can feed a readiness-style view of personnel health (similar to asset readiness): “who is trending toward failure and why.” This integrates into the broader ecosystem as a “human readiness” layer alongside equipment readiness.	
- Operational Scenario
    - During a long dismounted movement in high heat, each soldier wears a sensor suite (HR/HRV, skin temp, core-temp proxy, SpO₂, accelerometer) plus ambient sensors (WBGT/temperature/humidity). A small edge device (phone-class or rugged hub) runs an on-device model to detect heat strain and fatigue trends. When risk crosses threshold, the system generates an alert: “Soldier 12: heat stress probability 0.82; recommend rest + hydration in 10 min.” Squad leader sees a simple status map (green/yellow/red) and the medic receives triage-ranked alerts even without connectivity. When comms return, summarized events sync to the backend for trend analysis and after-action review.	SAP

- Title
    - Maintenance Execution Capture (Close the Paper-to-System Gap at the edge)	
- Problem Statement
    - Maintenance work is completed in the real world but not recorded in the system, leaving orders “open” incorrectly, inflating backlog, degrading readiness metrics, and causing planners to make decisions on stale data.	
- Context
    - Relies on SAP tables to infer open work and readiness. If confirmations and status updates lag behind reality, readiness charts and subgraphs become misleading (“ghost work”). Lightweight hardware capture improves data fidelity without changing the core systems.	
- Operational Scenario     
    - A technician completes an inspection and component swap on an aircraft/vehicle. Using a tablet + barcode scanner (or phone camera), they scan the equipment ID and work order, complete a guided checklist, and submit completion. A smart torque wrench uploads torque logs as proof-of-work. The system posts AFRU confirmations, updates JCDS statuses (e.g., released → technically complete), and closes related QMEL notifications. Agent Chief then shows a reduced backlog, improved readiness proxy, and updated network state for the asset/work center.	SAP

- Title
    - Hacking at the edge - finding non traditional realtime awareness information for civil protection and defense	Locating threats requires fusing all information that you can possible get. Often in defense systems are too isolated, and non-military systems are overlooked. We want to have absolutely everything, military or not. 	
- Context
    - github.com/projectqai Hydris provides a fully open source integration point for contributing sensor data into the NATO and real deployments in the Ukraine. We look outside of established capabilities into anything that can bring value, right now. You bring the data, we bring it to the real users comand systems. Absolutely anything that brings value is good, including your existing capabilities. You can run this  challenge in parallel with others, submitting the data to our CoP on the big screen.	
- Operational Scenario
    - Critical infrastructures has many different data sources everywhere. sensors, logistics, vehicles, checking machines, cameras, radars, social media, etc etc. We want to bring all of that data to the user and then make intelligent filtering decisions to highlight the data that indicates a specific geolocated threat, like drones	Project Q