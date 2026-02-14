#!/usr/bin/env python3
"""
Build a text-classification dataset from wearable health data for edge soldier-style monitoring.

Converts daily vitals (HR, SpO2, steps, intensity, sleep) into short text descriptions
and assigns risk levels (green / yellow / red) and recommendations using rule-based
proxies for heat stress and fatigue (aligned with challenge: heat strain, dehydration, fatigue).
Output is used to fine-tune MobileBERT for on-device risk classification and recommendations.
"""

import sys
from pathlib import Path

import pandas as pd

# Allow running from repo root or from data/
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_daily_summary():
    path = SCRIPT_DIR / "health_daily_summary.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df.dropna(subset=["Date"])


def vitals_to_text(row) -> str:
    """Turn one day's vitals into a short sentence for BERT (tokenizer-friendly)."""
    parts = []
    if pd.notna(row.get("HR_avg")) and row.get("HR_avg", 0) > 0:
        parts.append(f"HR average {int(row['HR_avg'])} bpm")
    if pd.notna(row.get("HR_max")) and row.get("HR_max", 0) > 0:
        parts.append(f"HR max {int(row['HR_max'])} bpm")
    if pd.notna(row.get("HR_resting")) and row.get("HR_resting", 0) > 0:
        parts.append(f"resting HR {int(row['HR_resting'])} bpm")
    if pd.notna(row.get("SpO2_avg")) and row.get("SpO2_avg", 0) > 0:
        parts.append(f"SpO2 {int(row['SpO2_avg'])} percent")
    if pd.notna(row.get("Steps")) and row.get("Steps", 0) > 0:
        parts.append(f"steps {int(row['Steps'])}")
    if pd.notna(row.get("Intensity_min")) and row.get("Intensity_min", 0) > 0:
        parts.append(f"active {int(row['Intensity_min'])} minutes")
    if pd.notna(row.get("Calories")) and row.get("Calories", 0) > 0:
        parts.append(f"calories {int(row['Calories'])}")
    if pd.notna(row.get("Sleep_total_min")) and row.get("Sleep_total_min", 0) > 0:
        h = int(row["Sleep_total_min"]) // 60
        m = int(row["Sleep_total_min"]) % 60
        parts.append(f"sleep {h}h{m}m")
    if not parts:
        return "No vital signs recorded."
    return " ".join(parts)


def assign_risk_and_recommendation(row) -> tuple[str, str]:
    """
    Rule-based risk (green/yellow/red) and recommendation text.
    Proxies for heat stress, dehydration, fatigue when ambient/WBGT not available.
    """
    hr_avg = float(row.get("HR_avg") or 0)
    hr_max = float(row.get("HR_max") or 0)
    hr_rest = float(row.get("HR_resting") or 0)
    spo2 = float(row.get("SpO2_avg") or 0)
    intensity = float(row.get("Intensity_min") or 0)
    sleep_min = float(row.get("Sleep_total_min") or 0)
    steps = float(row.get("Steps") or 0)

    # No data → treat as green / monitor
    if hr_avg <= 0 and hr_max <= 0 and spo2 <= 0 and intensity <= 0:
        return "green", "Continue normal activity. Stay hydrated."

    risk = "green"
    # Red: severe strain indicators
    if (hr_avg > 100 or hr_max > 120) or (spo2 > 0 and spo2 < 90) or (intensity > 45 and sleep_min < 30):
        risk = "red"
    # Yellow: elevated strain
    elif (
        (85 < hr_avg <= 100 or 100 < hr_max <= 120)
        or (90 <= spo2 < 95 and spo2 > 0)
        or (intensity > 20 and sleep_min < 60)
        or (steps > 5000 and hr_avg > 80 and sleep_min < 300)
    ):
        risk = "yellow" if risk == "green" else risk

    if risk == "red":
        rec = "Heat stress or fatigue risk. Rest and rehydrate. Seek shade. Recommend rest in 10 min."
    elif risk == "yellow":
        rec = "Monitor vital signs. Consider rest and hydration soon."
    else:
        rec = "Continue normal activity. Stay hydrated."

    return risk, rec


def synthetic_examples() -> list[dict]:
    """Add synthetic examples so all three risk levels appear in training (red was missing)."""
    return [
        {"text": "HR average 65 bpm HR max 82 resting HR 55 SpO2 98 percent steps 1500 active 5 minutes sleep 7h", "risk_level": "green", "recommendation": "Continue normal activity. Stay hydrated."},
        {"text": "HR average 70 bpm HR max 90 SpO2 97 percent steps 2000 sleep 6h", "risk_level": "green", "recommendation": "Continue normal activity. Stay hydrated."},
        {"text": "HR average 108 bpm HR max 125 SpO2 87 percent steps 8000 active 50 minutes sleep 0h", "risk_level": "red", "recommendation": "Heat stress or fatigue risk. Rest and rehydrate. Seek shade. Recommend rest in 10 min."},
        {"text": "HR average 105 bpm HR max 122 SpO2 88 percent active 45 minutes", "risk_level": "red", "recommendation": "Heat stress or fatigue risk. Rest and rehydrate. Seek shade. Recommend rest in 10 min."},
        {"text": "HR average 102 bpm HR max 118 SpO2 89 percent steps 7000 sleep 0h30m", "risk_level": "red", "recommendation": "Heat stress or fatigue risk. Rest and rehydrate. Seek shade. Recommend rest in 10 min."},
    ]


def build_dataset(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        text = vitals_to_text(row)
        risk, rec = assign_risk_and_recommendation(row)
        rows.append({"text": text, "risk_level": risk, "recommendation": rec})
    # Append synthetic examples so red (and clear green) are present for training
    rows.extend(synthetic_examples())
    return pd.DataFrame(rows)


def main():
    df = load_daily_summary()
    if df.empty:
        print("No health_daily_summary.csv found. Run data/health_insights.py first.")
        return 1
    out = build_dataset(df)
    out_path = SCRIPT_DIR / "health_risk_dataset.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {len(out)} examples to {out_path}")
    print(out.groupby("risk_level").size())
    return 0


if __name__ == "__main__":
    sys.exit(main())
