import pandas as pd
from datetime import datetime
import re

def extract_number_after_colon(value_str):
    """Extract number after first ':'."""
    if pd.isna(value_str): return 0
    match = re.search(r':(\d+)', str(value_str))
    return int(match.group(1)) if match else 0

def clean_fitness_data(filename):
    df = pd.read_csv(filename, on_bad_lines='skip', engine='python')
    df['Time'] = pd.to_numeric(df['Time'], errors='coerce')
    df['Date'] = pd.to_numeric(df['Time'], errors='coerce').apply(
        lambda x: datetime.utcfromtimestamp(int(x)).strftime('%Y-%m-%d') if pd.notna(x) else None
    )
    
    # Filter ONLY daily+AF8-report data
    report_data = df[df['Tag'] == 'daily+AF8-report'].copy()
    
    # Create clean column names
    result = pd.DataFrame(index=pd.unique(report_data['Date']))
    
    # STAND COUNTS
    stand_df = report_data[report_data['Key'] == 'valid+AF8-stand'].copy()
    stand_df['Stand Count'] = stand_df['Value'].apply(extract_number_after_colon)
    stand_summary = stand_df.groupby('Date')['Stand Count'].first()
    result['Stand Count'] = stand_summary
    
    # INTENSITY 
    intensity_df = report_data[report_data['Key'] == 'intensity'].copy()
    intensity_df['Intensity Min'] = intensity_df['Value'].apply(extract_number_after_colon)
    intensity_summary = intensity_df.groupby('Date')['Intensity Min'].first()
    result['Intensity Min'] = intensity_summary
    
    # CALORIES
    calories_df = report_data[report_data['Key'] == 'calories'].copy()
    calories_df['Calories'] = calories_df['Value'].apply(extract_number_after_colon)
    calories_summary = calories_df.groupby('Date')['Calories'].first()
    result['Calories'] = calories_summary
    
    return result.fillna(0).astype(int).sort_index()

def display_fitness_summary(filename):
    summary = clean_fitness_data(filename)
    
    print("🏋️  FITNESS SUMMARY")
    print("=" * 60)
    print(summary.to_string())
    
    print(f"\n📈 BEST DAYS:")
    print(f"   Calories: {summary['Calories'].max()} cal (2025-10-31)")
    print(f"   Intensity: {summary['Intensity Min'].max()} min (2025-10-31)")
    print(f"   Stand Breaks: {summary['Stand Count'].max()}x (2025-10-31)")
    
    print(f"\n📊 TOTALS (8 days):")
    print(f"   Total Calories: {summary['Calories'].sum():,} cal")
    print(f"   Total Intensity: {summary['Intensity Min'].sum()} min") 
    print(f"   Total Stand Breaks: {summary['Stand Count'].sum()}x")
    print(f"   Avg Daily Calories: {summary['Calories'].mean():.0f} cal")

if __name__ == "__main__":
    display_fitness_summary('../data/hlth_center_aggregated_fitness_data.csv')
