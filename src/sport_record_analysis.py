import pandas as pd
import re
from datetime import datetime
import os

def parse_encoded_value(encoded_str):
    """Decode URL-encoded fitness data"""
    encoded_str = encoded_str.strip('+,').replace('+AH0-', '').replace('+ACI-', '')
    
    # Extract key:value pairs
    pattern = r'([^-+]+):([0-9]+)'
    matches = re.findall(pattern, encoded_str)
    
    result = {}
    key_mapping = {
        'avg_hrm': 'avg_hrm',
        'max_hrm': 'max_hrm', 
        'min_hrm': 'min_hrm',
        'duration': 'duration',
        'calories': 'calories',
        'hrm_warm_up_duration': 'warm_up_duration',
        'hrm_fat_burning_duration': 'fat_burning_duration',
        'hrm_aerobic_duration': 'aerobic_duration',
        'hrm_anaerobic_duration': 'anaerobic_duration',
        'hrm_extreme_duration': 'extreme_duration'
    }
    
    for key, value in matches:
        clean_key = key.replace('-', '_')
        if clean_key in key_mapping:
            result[key_mapping[clean_key]] = int(value)
        else:
            result[clean_key] = int(value)
    
    return result

def process_badminton_csv(csv_file_path):
    """Process badminton CSV file and create clean analysis table"""
    
    # Read the CSV file
    df_raw = pd.read_csv(csv_file_path)
    
    sessions = []
    for index, row in df_raw.iterrows():
        data = parse_encoded_value(row['Value'])
        data['session_id'] = index + 1
        data['start_time'] = row['Time']
        
        # Convert durations to minutes
        duration_keys = ['duration', 'warm_up_duration', 'fat_burning_duration', 
                        'aerobic_duration', 'anaerobic_duration', 'extreme_duration']
        for key in duration_keys:
            if key in data:
                data[f'{key}_min'] = data[key] / 60.0
        
        sessions.append(data)
    
    # Create clean DataFrame
    df_clean = pd.DataFrame(sessions)
    
    # Select key columns for display
    display_cols = [
        'session_id',
        'start_time',
        'duration_min',
        'avg_hrm',
        'max_hrm',
        'calories',
        'warm_up_duration_min',
        'fat_burning_duration_min',
        'aerobic_duration_min',
        'anaerobic_duration_min',
        'extreme_duration_min'
    ]
    
    # Filter available columns
    available_cols = [col for col in display_cols if col in df_clean.columns]
    df_display = df_clean[available_cols].round(1)
    
    # Rename columns for readability
    rename_dict = {
        'session_id': 'Session',
        'start_time': 'Start Time',
        'duration_min': 'Duration (min)',
        'avg_hrm': 'Avg HR',
        'max_hrm': 'Max HR',
        'calories': 'Calories',
        'warm_up_duration_min': 'Warm-up (min)',
        'fat_burning_duration_min': 'Fat Burn (min)',
        'aerobic_duration_min': 'Aerobic (min)',
        'anaerobic_duration_min': 'Anaerobic (min)',
        'extreme_duration_min': 'Extreme (min)'
    }
    
    df_display = df_display.rename(columns=rename_dict)
    
    # Save clean CSV
    output_file = csv_file_path.replace('.csv', '_clean.csv')
    df_display.to_csv(output_file, index=False)
    print(f"✅ Clean CSV saved: {output_file}")
    
    return df_display

# MAIN EXECUTION
if __name__ == "__main__":
    # Replace with your CSV file path
    csv_file = "../data/hlth_center_sport_record.csv"  # Put your file here
    
    if os.path.exists(csv_file):
        print("🏸 Processing your badminton CSV file...")
        print("=" * 60)
        
        # Process and display table
        table = process_badminton_csv(csv_file)
        
        print("\n📊 YOUR BADMINTON SESSIONS:")
        print("-" * 60)
        print(table.to_string(index=False))
        
        # Summary stats
        print("\n📈 SUMMARY STATISTICS:")
        print("-" * 30)
        summary_cols = ['Duration (min)', 'Avg HR', 'Calories']
        available_summary = [col for col in summary_cols if col in table.columns]
        print(table[available_summary].describe().round(1))
        
    else:
        print(f"❌ File not found: {csv_file}")
        print("💡 Save your data as 'badminton_data.csv' in the same folder")
