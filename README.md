# fraud-investigation-agent
An AI-powered fraud investigation console that mirrors how a real fraud
analyst works. Every flagged transaction gets an ML risk score (XGBoost,
99% precision / 97.8% recall), then a LangGraph-orchestrated pipeline of
six specialized agents gathers concrete evidence — spending anomalies,
velocity spikes, device/IP fan-out, impossible travel, network patterns —
and blends it into a deterministic risk score and recommendation. A human
analyst always makes the final call; the AI investigates and explains,
it never executes. Built on 100,000 synthetic transactions with 8 real
fraud patterns, fully deployed on Vercel + Render + Supabase.
