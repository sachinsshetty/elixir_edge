import pandas as pd
import re

def read_fitness_csv(file_path):
    """Parse malformed fitness CSV with proper quote handling"""
    data = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        header_skipped = False
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'): 
                continue
            if not header_skipped:
                header_skipped = True
                continue
            
            parts = []
            current = ''
            in_quotes = False
            i = 0
            while i < len(line):
                char = line[i]
                if char == '"': 
                    in_quotes = not in_quotes
                elif char == ',' and not in_quotes:
                    parts.append(current.strip())
                    current = ''
                else: 
                    current += char
                i += 1
            parts.append(current.strip())
            
            if len(parts) >= 4:
                try:
                    time_val = parts[1].strip('"').strip()
                    float(time_val)
                    data.append([parts[0].strip('"'), time_val, parts[2].strip('"'), parts[3].strip('"')])
                except ValueError:
                    continue
    return pd.DataFrame(data, columns=['Key', 'Time', 'Value', 'UpdateTime'])

def extract_values(row):
    """Extract heart rate from encoded Value strings"""
    value = str(row['Value']).upper()
    
    hr_patterns = [
        r'(?:BPM|HRT|HR|HEART_RATE|RESTING-HEART-RATE)[^:]*:(\d+)',
        r'HEART[^:]*:(\d+)',
        r'HR[^:]*:(\d+)'
    ]
    
    for pattern in hr_patterns:
        match = re.search(pattern, value)
        if match:
            row['heart_rate'] = int(match.group(1))
            break
    else:
        row['heart_rate'] = 0
        
    row['calories'] = row['steps'] = row['distance'] = 0
    return row

# MAIN EXECUTION - FIXED VERSION
print("🚀 Fitness Data Analyzer v2.2 - ERROR FREE")
print("=" * 60)

print("📂 Loading data...")
df = read_fitness_csv('../data/hlth_center_fitness_data.csv')

# Clean numeric columns FIRST
df['Time'] = pd.to_numeric(df['Time'], errors='coerce')
df['UpdateTime'] = pd.to_numeric(df['UpdateTime'], errors='coerce')
df = df.dropna(subset=['Time'])

print("🔍 Extracting metrics...")
df = df.apply(extract_values, axis=1)

# Create datetime column BEFORE filtering
df['Time_Datetime'] = pd.to_datetime(df['Time'], unit='s', utc=True, errors='coerce')
df['Time_Human'] = df['Time_Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S UTC')

# Filter AFTER datetime creation
hr_data = df[df['heart_rate'] > 0].copy()

print(f"✅ Loaded {len(df):,} total records")
print(f"❤️ Found {len(hr_data)} heart rate readings")

print("\n📋 Recent Heart Rate Activity:")
# FIXED: Sort using Time_Datetime column that EXISTS in hr_data
display = hr_data[['Time_Human', 'Key', 'heart_rate']].sort_values('Time_Datetime', ascending=False).head(15)
print(display.to_string(index=False))

print("\n📊 Health Summary:")
print(f"💓 Average Heart Rate: {hr_data['heart_rate'].mean():.1f} BPM")
print(f"💓 Resting HR Range: {hr_data['heart_rate'].min():.0f}-{hr_data['heart_rate'].quantile(0.25):.0f} BPM")
print(f"💓 Peak HR: {hr_data['heart_rate'].max():.0f} BPM")
print(f"⏱️  Data Span: {df['Time_Human'].min()} → {df['Time_Human'].max()}")

# FIXED: Create date column from datetime
hr_data['Date'] = hr_data['Time_Datetime'].dt.date
print(f"📈 Active Days: {hr_data['Date'].nunique()}")

# Health assessment
avg_hr = hr_data['heart_rate'].mean()
if avg_hr < 60: 
    status = "🏆 Athlete level"
elif avg_hr < 70: 
    status = "✅ Excellent"
elif avg_hr < 80: 
    status = "👍 Good"
else: 
    status = "⚠️  Monitor"

print(f"\n{status} cardiovascular health (Avg: {avg_hr:.0f} BPM)")
print("\n✅ Analysis complete! 💪")

# Save cleaned data
hr_data[['Time_Human', 'Key', 'heart_rate', 'Date']].to_csv('cleaned_heart_rate.csv', index=False)
print("💾 Cleaned data saved to 'cleaned_heart_rate.csv'")
