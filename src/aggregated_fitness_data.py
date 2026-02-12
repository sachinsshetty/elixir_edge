import pandas as pd
import urllib.parse
from datetime import datetime
import json
import re

def parse_value(value_str):
    """Decode URL-encoded string and extract key-value pairs."""
    # Decode URL encoding (%XX -> char, + -> space)
    decoded = urllib.parse.unquote(value_str.replace('+', '%'))
    # Extract key:value pairs like "key-:123"
    pairs = re.findall(r'([a-zA-Z0-9_-]+):([0-9.-]+)', decoded)
    return dict(pairs)

def unix_to_date(timestamp):
    """Convert Unix timestamp to readable date."""
    return datetime.utcfromtimestamp(int(timestamp)).strftime('%Y-%m-%d')

def ingest_and_display(filename):
    """Ingest CSV file and display key tables."""
    
    # Read raw CSV
    df = pd.read_csv(filename)
    
    # Add human-readable date column
    df['Date'] = df['Time'].apply(unix_to_date)
    
    print("=== STEPS DATA ===")
    steps_df = df[df['Tag'] == 'daily+AF8-report'][df['Key'] == 'steps']
    steps_data = []
    for _, row in steps_df.iterrows():
        data = parse_value(row['Value'])
        steps_data.append({
            'Date': row['Date'],
            'Steps': data.get('steps', 0),
            'Distance': data.get('distance', 0),
            'Calories': data.get('calories', 0)
        })
    steps_table = pd.DataFrame(steps_data)
    print(steps_table.to_string(index=False))
    
    print("\n=== HEART RATE DATA ===")
    hr_df = df[df['Tag'] == 'daily+AF8-report'][df['Key'] == 'heart+AF8-rate']
    hr_data = []
    for _, row in hr_df.iterrows():
        data = parse_value(row['Value'])
        hr_data.append({
            'Date': row['Date'],
            'Avg HR': data.get('avg+AF8-hr', data.get('avg+AF8hr', 0)),
            'Min HR': data.get('min+AF8-hr', data.get('min+AF8hr', 0)),
            'Max HR': data.get('max+AF8-hr', data.get('max+AF8hr', 0))
        })
    hr_table = pd.DataFrame(hr_data)
    print(hr_table.to_string(index=False))
    
    print("\n=== CALORIES BURNED ===")
    cal_df = df[df['Tag'] == 'daily+AF8-report'][df['Key'] == 'calories']
    cal_data = []
    for _, row in cal_df.iterrows():
        data = parse_value(row['Value'])
        cal_data.append({'Date': row['Date'], 'Calories': data.get('calories', 0)})
    cal_table = pd.DataFrame(cal_data)
    print(cal_table.to_string(index=False))
    
    print("\n=== FULL RAW DATA SAMPLE ===")
    print(df[['Tag', 'Key', 'Date', 'Value']].head(10).to_string(index=False))

# Usage
if __name__ == "__main__":
    ingest_and_display('../data/hlth_center_aggregated_fitness_data.csv')
