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


def _rec_green() -> str:
    return "Continue normal activity. Stay hydrated."
def _rec_yellow() -> str:
    return "Monitor vital signs. Consider rest and hydration soon."
def _rec_red() -> str:
    return "Heat stress or fatigue risk. Rest and rehydrate. Seek shade. Recommend rest in 10 min."


def synthetic_examples() -> list[dict]:
    """
    Soldier-relevant synthetic vitals for robust training.
    Covers heat stress, dehydration, fatigue, dismounted movement, and rest scenarios.
    """
    return [
        # --- GREEN: rest, light duty, good recovery ---
        {"text": "HR average 58 bpm HR max 75 resting HR 52 SpO2 99 percent steps 1200 active 3 minutes sleep 7h", "risk_level": "green", "recommendation": _rec_green()},
        {"text": "HR average 62 bpm HR max 80 SpO2 98 percent steps 2000 sleep 6h30m", "risk_level": "green", "recommendation": _rec_green()},
        {"text": "HR average 65 bpm HR max 82 resting HR 55 SpO2 98 percent steps 1500 active 5 minutes sleep 7h", "risk_level": "green", "recommendation": _rec_green()},
        {"text": "HR average 68 bpm HR max 88 resting HR 60 SpO2 97 percent steps 2500 active 8 minutes sleep 6h", "risk_level": "green", "recommendation": _rec_green()},
        {"text": "HR average 70 bpm HR max 90 SpO2 97 percent steps 3000 sleep 6h", "risk_level": "green", "recommendation": _rec_green()},
        {"text": "HR average 72 bpm HR max 92 resting HR 64 steps 1800 active 10 minutes sleep 8h", "risk_level": "green", "recommendation": _rec_green()},
        {"text": "HR average 75 bpm HR max 95 SpO2 96 percent steps 3500 active 12 minutes calories 180 sleep 5h30m", "risk_level": "green", "recommendation": _rec_green()},
        {"text": "HR average 78 bpm HR max 98 resting HR 66 steps 4000 active 15 minutes sleep 5h", "risk_level": "green", "recommendation": _rec_green()},
        {"text": "SpO2 98 percent steps 2200 sleep 7h calories 150", "risk_level": "green", "recommendation": _rec_green()},
        {"text": "HR average 64 bpm HR max 78 SpO2 99 percent active 2 minutes sleep 8h", "risk_level": "green", "recommendation": _rec_green()},
        # --- YELLOW: sustained effort, monitor ---
        {"text": "HR average 84 bpm HR max 102 SpO2 96 percent steps 5500 active 22 minutes sleep 4h", "risk_level": "yellow", "recommendation": _rec_yellow()},
        {"text": "HR average 86 bpm HR max 108 resting HR 72 steps 6000 active 25 minutes sleep 3h30m", "risk_level": "yellow", "recommendation": _rec_yellow()},
        {"text": "HR average 88 bpm HR max 105 SpO2 95 percent steps 5000 active 25 minutes sleep 4h", "risk_level": "yellow", "recommendation": _rec_yellow()},
        {"text": "HR average 90 bpm HR max 112 resting HR 78 steps 6500 active 28 minutes calories 420 sleep 3h", "risk_level": "yellow", "recommendation": _rec_yellow()},
        {"text": "HR average 92 bpm HR max 115 SpO2 94 percent steps 7000 active 30 minutes sleep 2h", "risk_level": "yellow", "recommendation": _rec_yellow()},
        {"text": "HR average 82 bpm HR max 105 resting HR 69 steps 2276 active 17 minutes calories 175", "risk_level": "yellow", "recommendation": _rec_yellow()},
        {"text": "HR average 85 bpm HR max 100 SpO2 93 percent steps 4500 active 35 minutes sleep 1h", "risk_level": "yellow", "recommendation": _rec_yellow()},
        {"text": "HR average 87 bpm HR max 110 resting HR 74 steps 5800 active 20 minutes sleep 4h", "risk_level": "yellow", "recommendation": _rec_yellow()},
        {"text": "HR average 91 bpm HR max 118 SpO2 94 percent active 38 minutes sleep 2h30m", "risk_level": "yellow", "recommendation": _rec_yellow()},
        {"text": "HR average 83 bpm HR max 98 steps 5200 active 24 minutes sleep 5h", "risk_level": "yellow", "recommendation": _rec_yellow()},
        {"text": "HR average 89 bpm HR max 106 SpO2 95 percent steps 6200 active 26 minutes calories 380", "risk_level": "yellow", "recommendation": _rec_yellow()},
        {"text": "HR average 94 bpm HR max 116 resting HR 80 steps 7500 active 32 minutes sleep 1h30m", "risk_level": "yellow", "recommendation": _rec_yellow()},
        # --- RED: heat stress, exhaustion, low SpO2 ---
        {"text": "HR average 108 bpm HR max 125 SpO2 87 percent steps 8000 active 50 minutes sleep 0h", "risk_level": "red", "recommendation": _rec_red()},
        {"text": "HR average 105 bpm HR max 122 SpO2 88 percent active 45 minutes", "risk_level": "red", "recommendation": _rec_red()},
        {"text": "HR average 102 bpm HR max 118 SpO2 89 percent steps 7000 sleep 0h30m", "risk_level": "red", "recommendation": _rec_red()},
        {"text": "HR average 112 bpm HR max 128 SpO2 86 percent steps 9000 active 55 minutes sleep 0h", "risk_level": "red", "recommendation": _rec_red()},
        {"text": "HR average 110 bpm HR max 130 resting HR 95 SpO2 85 percent steps 8500 active 52 minutes", "risk_level": "red", "recommendation": _rec_red()},
        {"text": "HR average 106 bpm HR max 124 SpO2 88 percent active 48 minutes sleep 0h20m", "risk_level": "red", "recommendation": _rec_red()},
        {"text": "HR average 115 bpm HR max 132 SpO2 84 percent steps 10000 active 60 minutes calories 650", "risk_level": "red", "recommendation": _rec_red()},
        {"text": "HR average 104 bpm HR max 120 SpO2 87 percent steps 7200 active 46 minutes sleep 0h", "risk_level": "red", "recommendation": _rec_red()},
        {"text": "HR average 118 bpm HR max 135 SpO2 83 percent active 58 minutes sleep 0h15m", "risk_level": "red", "recommendation": _rec_red()},
        {"text": "HR average 100 bpm HR max 121 SpO2 86 percent steps 6800 active 50 minutes sleep 0h25m", "risk_level": "red", "recommendation": _rec_red()},
        {"text": "SpO2 85 percent HR average 109 bpm HR max 126 steps 7800 active 54 minutes", "risk_level": "red", "recommendation": _rec_red()},
        {"text": "HR average 113 bpm HR max 129 SpO2 86 percent resting HR 92 active 56 minutes sleep 0h", "risk_level": "red", "recommendation": _rec_red()},
        # --- Edge / borderline (soldier in transition) ---
        {"text": "HR average 98 bpm HR max 119 SpO2 91 percent steps 6000 active 42 minutes sleep 0h45m", "risk_level": "yellow", "recommendation": _rec_yellow()},
        {"text": "HR average 97 bpm HR max 118 SpO2 92 percent active 40 minutes sleep 1h", "risk_level": "yellow", "recommendation": _rec_yellow()},
        {"text": "HR average 80 bpm HR max 96 resting HR 68 steps 4200 active 18 minutes sleep 5h", "risk_level": "green", "recommendation": _rec_green()},
        {"text": "HR average 99 bpm HR max 120 SpO2 90 percent steps 6500 active 44 minutes sleep 0h30m", "risk_level": "red", "recommendation": _rec_red()},
        {"text": "HR average 81 bpm HR max 99 steps 3800 active 16 minutes sleep 5h30m", "risk_level": "green", "recommendation": _rec_green()},
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
