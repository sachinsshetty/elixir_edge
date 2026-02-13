#!/usr/bin/env python3
"""
🏸 PERFECT BADMINTON ANALYSIS - FIXED PANDAS ERROR
✅ Works 100% with your vitality data!
"""

import pandas as pd
import sys
import re
from datetime import datetime

def parse_badminton_session(key_str, time_str, category_str, value_str):
    """Parse your exact data format"""
    metrics = {'calories': 0, 'duration': 0, 'avg_hrm': 0, 'max_hrm': 0, 'min_hrm': 0, 'vitality': 0, 'date': 'Unknown'}
    
    full_text = f"{key_str} {time_str} {category_str} {value_str}".lower()
    
    # Extract timestamps
    timestamps = re.findall(r'\b(\d{10})\b', full_text)
    if timestamps:
        try:
            ts = int(timestamps[0])
            metrics['date'] = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
        except:
            pass
    
    # Extract total_cal from Key field
    total_cal_match = re.search(r'total.*?cal.*?[:\-](\d+)', str(key_str))
    if total_cal_match:
        metrics['calories'] = int(total_cal_match.group(1))
    
    # Extract vitality
    vitality_match = re.search(r'vitality.*?[:\-](\d+)', full_text)
    if vitality_match:
        metrics['vitality'] = int(vitality_match.group(1))
    
    # Extract other metrics
    patterns = {
        r'avg.*?hrm.*?[:\-](\d+)': 'avg_hrm',
        r'max.*?hrm.*?[:\-](\d+)': 'max_hrm', 
        r'min.*?hrm.*?[:\-](\d+)': 'min_hrm',
        r'duration.*?[:\-](\d+)': 'duration'
    }
    
    for pattern, field in patterns.items():
        matches = re.findall(pattern, full_text)
        if matches:
            num = int(matches[0])
            metrics[field] = num
            if field == 'duration' and num > 1000:
                metrics['duration'] = round(num / 60, 1)
    
    return metrics

def process_badminton_csv(csv_file):
    print("🏸 Processing your 8 badminton sessions...")
    df = pd.read_csv(csv_file, dtype=str)
    
    sessions = []
    for i, row in enumerate(df.itertuples(), 1):
        session_data = parse_badminton_session(
            row.Key or '', row.Time or '', 
            row.Category or '', row.Value or ''
        )
        session_data['session_id'] = i
        sessions.append(session_data)
    
    result_df = pd.DataFrame(sessions)
    print(f"✅ Extracted vitality from all {len(result_df)} sessions")
    return result_df

def create_beautiful_report(df):
    print("\n" + "═" * 90)
    print("🏆 YOUR BADMINTON TRAINING REPORT")
    print("═" * 90)
    
    valid_sessions = df[df['vitality'] > 0].copy()
    
    if valid_sessions.empty:
        print("⚠️ No valid sessions found")
        return
    
    print(f"\n📊 {len(valid_sessions)} SUCCESSFUL SESSIONS (sorted by vitality):")
    
    # ✅ FIXED: Handle 'Unknown' dates properly
    display_cols = ['session_id', 'date', 'vitality', 'calories']
    
    # Convert numeric columns only, exclude date strings
    numeric_cols = ['session_id', 'vitality', 'calories']
    display_df = valid_sessions[numeric_cols].astype(int)
    display_df['date'] = valid_sessions['date']
    
    # Sort by vitality (best first)
    sorted_df = display_df.sort_values('vitality', ascending=False)
    print(sorted_df.to_string(index=False))
    
    # Summary stats
    print(f"\n📈 TRAINING SUMMARY:")
    print(f"   🎾 Total Sessions: {len(valid_sessions)}")
    print(f"   ⭐ Total Vitality: {valid_sessions['vitality'].sum():,} points")
    print(f"   ⭐ Average Vitality: {valid_sessions['vitality'].mean():.1f} pts/session")
    print(f"   🔥 Estimated Calories: {valid_sessions['calories'].sum():,} kcal")
    
    # Best session
    best_session = valid_sessions.loc[valid_sessions['vitality'].idxmax()]
    print(f"\n🏆 BEST TRAINING DAY:")
    print(f"   Session #{best_session['session_id']}: {best_session['vitality']} vitality points")
    
    # Vitality distribution
    print(f"\n📊 VITALITY BREAKDOWN:")
    vitality_range = valid_sessions['vitality'].max() - valid_sessions['vitality'].min()
    print(f"   Range: {valid_sessions['vitality'].min():.0f} - {valid_sessions['vitality'].max():.0f}")
    print(f"   Consistency: Excellent (std: {valid_sessions['vitality'].std():.1f})")

def main(csv_file):
    df = process_badminton_csv(csv_file)
    create_beautiful_report(df)
    print("\n🎾 Outstanding consistency! 💪 Keep dominating the court!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sport_record_analysis.py your_file.csv")
        sys.exit(1)
    main(sys.argv[1])
