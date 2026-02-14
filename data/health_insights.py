#!/usr/bin/env python3
"""
Redmi Watch 5 Lite – Health data analysis.

Reads health/fitness CSVs from the data/ folder (exported from the device),
parses the encoded Value fields, and prints a consolidated health report:
steps, calories, heart rate, sleep, SpO2, sport sessions, stand reminders.
"""

import re
from datetime import datetime
from pathlib import Path

import pandas as pd


# --- Helpers for encoded Value strings (device uses +AF8- = underscore, :N for numbers) ---

def extract_first_number(value_str):
    """First number after a colon in the Value string."""
    if pd.isna(value_str):
        return 0
    m = re.search(r":(\d+)", str(value_str))
    return int(m.group(1)) if m else 0


# --- Data paths (run from repo root or data/) ---

def data_dir():
    d = Path(__file__).resolve().parent
    if (d / "hlth_center_aggregated_fitness_data.csv").exists():
        return d
    return d.parent / "data"


# --- Load & parse Aggregated (daily report) ---

def _read_csv_value_in_middle(path, num_fixed_start=3, num_fixed_end=1):
    """Read CSV where one field (Value) contains commas; Value is between fixed start and end columns.
    Returns list of dicts with keys from header; Value = everything between start and end columns.
    Header: first line. Each row: parts[0:num_fixed_start], Value=join(parts[num_fixed_start:-num_fixed_end]), parts[-num_fixed_end:].
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        return []
    header = lines[0].split(",")
    # Header has 5 names but Value may contain commas; we use structure: first 3, last 1, middle=Value
    rows = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < num_fixed_start + num_fixed_end:
            continue
        start_vals = parts[:num_fixed_start]
        end_vals = parts[-num_fixed_end:]
        value_str = ",".join(parts[num_fixed_start : -num_fixed_end])
        if len(header) == 5:
            row = {
                header[0]: start_vals[0],
                header[1]: start_vals[1],
                header[2]: start_vals[2],
                "Value": value_str,
                header[4]: end_vals[0],
            }
        else:
            row = dict(zip(header[:num_fixed_start], start_vals))
            row["Value"] = value_str
            row[header[-1]] = end_vals[0]
        rows.append(row)
    return rows


def load_aggregated(data_path):
    path = data_path / "hlth_center_aggregated_fitness_data.csv"
    if not path.exists():
        return pd.DataFrame()
    # Value contains commas; pandas would truncate. Parse manually: Tag,Key,Time, Value..., UpdateTime
    rows = _read_csv_value_in_middle(path, num_fixed_start=3, num_fixed_end=1)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["Time"] = pd.to_numeric(df["Time"], errors="coerce")
    df = df.dropna(subset=["Time"])
    df["Date"] = df["Time"].apply(
        lambda x: datetime.utcfromtimestamp(int(x)).strftime("%Y-%m-%d")
    )
    return df


# --- Steps/calories from aggregated (correct parsing) ---

def parse_steps_row(value_str):
    """Value for Key=steps is like ...calories+ACIAIg-:101,+ACIAIg-distance+ACIAIg-:1715,+ACIAIg-steps+ACIAIg-:2276."""
    if pd.isna(value_str):
        return 0, 0, 0
    s = str(value_str)
    cal = re.search(r"calories\+ACIAIg-:(\d+)", s)
    dist = re.search(r"distance\+ACIAIg-:(\d+)", s)
    steps = re.search(r"steps\+ACIAIg-:(\d+)", s)
    return (
        int(steps.group(1)) if steps else 0,
        int(dist.group(1)) if dist else 0,
        int(cal.group(1)) if cal else 0,
    )


def build_daily_summary(agg_df):
    """Build clean daily summary from aggregated CSV."""
    report = agg_df[agg_df["Tag"] == "daily+AF8-report"].copy()
    if report.empty:
        return pd.DataFrame()

    report["KeyNorm"] = report["Key"].str.replace(r"\+AF8\-", "_", regex=True)
    report["Time"] = pd.to_numeric(report["Time"], errors="coerce")
    report["Date"] = report["Time"].apply(
        lambda x: datetime.utcfromtimestamp(int(x)).strftime("%Y-%m-%d")
    )

    days = sorted(report["Date"].unique())
    rows = []

    for day in days:
        d = report[report["Date"] == day]
        row = {"Date": day}

        # Steps
        s = d[d["KeyNorm"] == "steps"]
        if not s.empty:
            st, dist, cal = parse_steps_row(s["Value"].iloc[0])
            row["Steps"] = st
            row["Distance_m"] = dist
            row["Steps_cal"] = cal
        else:
            row["Steps"] = row["Distance_m"] = row["Steps_cal"] = 0

        # Calories (daily)
        c = d[d["KeyNorm"] == "calories"]
        row["Calories"] = extract_first_number(c["Value"].iloc[0]) if not c.empty else 0

        # Stand
        v = d[d["KeyNorm"] == "valid_stand"]
        row["Stand_count"] = extract_first_number(v["Value"].iloc[0]) if not v.empty else 0

        # Intensity
        i = d[d["KeyNorm"] == "intensity"]
        row["Intensity_min"] = extract_first_number(i["Value"].iloc[0]) if not i.empty else 0

        # Heart rate
        hr = d[d["KeyNorm"] == "heart_rate"]
        if not hr.empty:
            v = hr["Value"].iloc[0]
            row["HR_avg"] = int(re.search(r"avg\+AF8-hr\+ACIAIg-:(\d+)", str(v)).group(1)) if re.search(r"avg\+AF8-hr\+ACIAIg-:(\d+)", str(v)) else 0
            row["HR_min"] = int(re.search(r"min\+AF8-hr\+ACIAIg-:(\d+)", str(v)).group(1)) if re.search(r"min\+AF8-hr\+ACIAIg-:(\d+)", str(v)) else 0
            row["HR_max"] = int(re.search(r"max\+AF8-hr\+ACIAIg-:(\d+)", str(v)).group(1)) if re.search(r"max\+AF8-hr\+ACIAIg-:(\d+)", str(v)) else 0
            rhr = re.search(r"avg\+AF8-rhr\+ACIAIg-:(\d+)", str(v))
            row["HR_resting"] = int(rhr.group(1)) if rhr else 0
        else:
            row["HR_avg"] = row["HR_min"] = row["HR_max"] = row["HR_resting"] = 0

        # Sleep
        sl = d[d["KeyNorm"] == "sleep"]
        if not sl.empty:
            v = sl["Value"].iloc[0]
            row["Sleep_total_min"] = int(re.search(r"total\+AF8-duration\+ACIAIg-:(\d+)", str(v)).group(1)) if re.search(r"total\+AF8-duration\+ACIAIg-:(\d+)", str(v)) else extract_first_number(v)
            row["Sleep_score"] = int(re.search(r"sleep\+AF8-score\+ACIAIg-:(\d+)", str(v)).group(1)) if re.search(r"sleep\+AF8-score\+ACIAIg-:(\d+)", str(v)) else 0
            row["Sleep_deep_min"] = int(re.search(r"sleep\+AF8-deep\+AF8-duration\+ACIAIg-:(\d+)", str(v)).group(1)) if re.search(r"sleep\+AF8-deep\+AF8-duration\+ACIAIg-:(\d+)", str(v)) else 0
            row["Sleep_light_min"] = int(re.search(r"sleep\+AF8-light\+AF8-duration\+ACIAIg-:(\d+)", str(v)).group(1)) if re.search(r"sleep\+AF8-light\+AF8-duration\+ACIAIg-:(\d+)", str(v)) else 0
        else:
            row["Sleep_total_min"] = row["Sleep_score"] = row["Sleep_deep_min"] = row["Sleep_light_min"] = 0

        # SpO2
        sp = d[d["KeyNorm"] == "spo2"]
        if not sp.empty:
            v = sp["Value"].iloc[0]
            m = re.search(r"avg\+AF8-spo2\+ACIAIg-:(\d+)", str(v))
            row["SpO2_avg"] = int(m.group(1)) if m else 0
        else:
            row["SpO2_avg"] = 0

        rows.append(row)

    return pd.DataFrame(rows)


# --- Sport sessions (badminton) ---

def load_sport_record(data_path):
    path = data_path / "hlth_center_sport_record.csv"
    if not path.exists():
        return pd.DataFrame()
    # Value contains commas; parse manually: Key,Time,Category, Value..., UpdateTime
    rows = _read_csv_value_in_middle(path, num_fixed_start=3, num_fixed_end=1)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.astype(str)


def parse_sport_sessions(sport_df):
    """Parse sport record into list of session dicts (calories, duration, avg_hr, vitality, date)."""
    if sport_df.empty or "Value" not in sport_df.columns:
        return []
    sessions = []
    for _, row in sport_df.iterrows():
        v = str(row.get("Value", ""))
        t = row.get("Time")
        date_str = datetime.utcfromtimestamp(int(t)).strftime("%Y-%m-%d %H:%M") if t and str(t).isdigit() else ""

        cal = re.search(r"calories\+ACIAIg-:(\d+)", v) or re.search(r"total\+AF8-cal\+ACIAIg-:(\d+)", v)
        dur = re.search(r"duration\+ACIAIg-:(\d+)", v)
        avg_hr = re.search(r"avg\+AF8-hrm\+ACIAIg-:(\d+)", v)
        max_hr = re.search(r"max\+AF8-hrm\+ACIAIg-:(\d+)", v)
        vitality = re.search(r"vitality\+ACIAIg-:(\d+)", v)

        sessions.append({
            "Date": date_str,
            "Calories": int(cal.group(1)) if cal else 0,
            "Duration_sec": int(dur.group(1)) if dur else 0,
            "Avg_HR": int(avg_hr.group(1)) if avg_hr else 0,
            "Max_HR": int(max_hr.group(1)) if max_hr else 0,
            "Vitality": int(vitality.group(1)) if vitality else 0,
        })
    return sessions


# --- Raw fitness (heart rate, steps) ---

def load_fitness(data_path):
    path = data_path / "hlth_center_fitness_data.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, on_bad_lines="skip", engine="python")
    df["Time"] = pd.to_numeric(df["Time"], errors="coerce")
    df = df.dropna(subset=["Time"])
    return df


def summarize_fitness(fitness_df):
    """Summarize raw fitness: HR stats, step count from keys heart_rate, steps, calories."""
    if fitness_df.empty:
        return {}
    df = fitness_df.copy()
    df["KeyNorm"] = df["Key"].str.replace(r"\+AF8\-", "_", regex=True)

    hr = df[df["KeyNorm"] == "heart_rate"]
    out = {"heart_rate_records": len(hr)}
    if not hr.empty:
        bpms = []
        for v in hr["Value"]:
            m = re.search(r"bpm\+ACIAIg-:(\d+)", str(v))
            if m:
                bpms.append(int(m.group(1)))
        if bpms:
            out["HR_avg"] = sum(bpms) / len(bpms)
            out["HR_min"] = min(bpms)
            out["HR_max"] = max(bpms)

    steps_df = df[df["KeyNorm"] == "steps"]
    total_steps = 0
    for v in steps_df["Value"]:
        m = re.search(r"steps\+ACIAIg-:(\d+)", str(v))
        if m:
            total_steps += int(m.group(1))
    out["Steps_total_raw"] = total_steps
    return out


# --- Main report ---

def print_health_report(summary_df, sport_sessions, fitness_summary):
    print()
    print("=" * 70)
    print("  REDMI WATCH 5 LITE – HEALTH INSIGHTS")
    print("=" * 70)

    if summary_df.empty and not sport_sessions and not fitness_summary:
        print("No data found. Place CSVs in the data/ folder.")
        return

    # Daily table
    if not summary_df.empty:
        print("\n📅 DAILY SUMMARY (aggregated)")
        print("-" * 70)
        display = summary_df[["Date", "Steps", "Calories", "Stand_count", "Intensity_min"]].copy()
        display.columns = ["Date", "Steps", "Cal (day)", "Stands", "Active (min)"]
        print(display.to_string(index=False))

        print("\n📈 TOTALS & AVERAGES")
        print("-" * 70)
        n = len(summary_df)
        print(f"   Days with data:     {n}")
        print(f"   Total steps:        {summary_df['Steps'].sum():,}")
        print(f"   Total calories:     {summary_df['Calories'].sum():,} kcal")
        print(f"   Avg steps/day:      {summary_df['Steps'].mean():.0f}")
        print(f"   Avg calories/day:   {summary_df['Calories'].mean():.0f}")
        print(f"   Total stand breaks: {summary_df['Stand_count'].sum():.0f}")
        print(f"   Total active min:   {summary_df['Intensity_min'].sum():.0f}")

        # Heart rate (from daily report)
        hr_days = summary_df[summary_df["HR_avg"] > 0]
        if not hr_days.empty:
            print("\n❤️  HEART RATE (daily report)")
            print("-" * 70)
            print(f"   Avg HR (across days): {hr_days['HR_avg'].mean():.0f} bpm")
            print(f"   Resting HR range:     {hr_days['HR_resting'].min():.0f}–{hr_days['HR_resting'].max():.0f} bpm")
            print(f"   Peak HR (daily max):  {hr_days['HR_max'].max():.0f} bpm")

        # Sleep
        sleep_days = summary_df[summary_df["Sleep_total_min"] > 0]
        if not sleep_days.empty:
            print("\n😴 SLEEP (when recorded)")
            print("-" * 70)
            total_min = sleep_days["Sleep_total_min"].sum()
            print(f"   Nights recorded:   {len(sleep_days)}")
            print(f"   Avg sleep:        {sleep_days['Sleep_total_min'].mean():.0f} min ({sleep_days['Sleep_total_min'].mean()/60:.1f} h)")
            print(f"   Avg score:         {sleep_days['Sleep_score'].mean():.0f}/100")
            if (sleep_days["Sleep_deep_min"] > 0).any():
                print(f"   Avg deep sleep:    {sleep_days['Sleep_deep_min'].mean():.0f} min")

        # SpO2
        spo2_days = summary_df[summary_df["SpO2_avg"] > 0]
        if not spo2_days.empty:
            print("\n🫁 SpO2")
            print("-" * 70)
            print(f"   Avg SpO2: {spo2_days['SpO2_avg'].mean():.0f}%")

    # Sport
    if sport_sessions:
        print("\n🏸 SPORT SESSIONS (e.g. badminton)")
        print("-" * 70)
        for i, s in enumerate(sport_sessions, 1):
            dur_min = s["Duration_sec"] / 60
            print(f"   {i}. {s['Date']}  |  {s['Calories']} cal  |  {dur_min:.0f} min  |  avg HR {s['Avg_HR']}  |  vitality {s['Vitality']}")
        total_cal = sum(x["Calories"] for x in sport_sessions)
        total_dur = sum(x["Duration_sec"] for x in sport_sessions) / 60
        print(f"   Total: {len(sport_sessions)} sessions, {total_cal} cal, {total_dur:.0f} min")

    # Raw fitness (if loaded)
    if fitness_summary:
        print("\n📊 RAW FITNESS DATA (time-series)")
        print("-" * 70)
        print(f"   Heart rate readings: {fitness_summary.get('heart_rate_records', 0)}")
        if "HR_avg" in fitness_summary:
            print(f"   HR avg/min/max:      {fitness_summary['HR_avg']:.0f} / {fitness_summary['HR_min']} / {fitness_summary['HR_max']} bpm")
        if fitness_summary.get("Steps_total_raw", 0) > 0:
            print(f"   Steps (from raw):    {fitness_summary['Steps_total_raw']:,}")

    print("\n" + "=" * 70)


def main():
    data_path = data_dir()
    if not data_path.exists():
        print("Data folder not found:", data_path)
        return

    # Load all sources
    agg_df = load_aggregated(data_path)
    summary_df = build_daily_summary(agg_df)
    sport_df = load_sport_record(data_path)
    sport_sessions = parse_sport_sessions(sport_df)
    fitness_df = load_fitness(data_path)
    fitness_summary = summarize_fitness(fitness_df)

    print_health_report(summary_df, sport_sessions, fitness_summary)

    # Optional: write daily summary CSV
    if not summary_df.empty:
        out_csv = data_path / "health_daily_summary.csv"
        summary_df.to_csv(out_csv, index=False)
        print(f"💾 Daily summary saved to {out_csv}")


if __name__ == "__main__":
    main()
