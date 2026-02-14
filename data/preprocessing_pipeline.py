import pandas as pd
import json
import html
from datetime import datetime
from typing import Dict, List, Tuple
import numpy as np

class HealthDataProcessor:
    """Process Redmi Watch health data for MobileBERT training"""
    
    def __init__(self, fitness_file: str, aggregated_file: str, sport_file: str):
        self.fitness_data = self._load_fitness_data(fitness_file)
        self.aggregated_data = pd.read_csv(aggregated_file, on_bad_lines='skip')
        self.sport_data = pd.read_csv(sport_file, on_bad_lines='skip')
    
    def _load_fitness_data(self, filepath: str) -> pd.DataFrame:
        """Load and parse fitness CSV with HTML-encoded JSON values"""
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        data_rows = []
        for line in lines[1:]:
            parts = line.strip().split(',', 3)
            if len(parts) >= 4:
                key, time, value, update_time = parts
                try:
                    decoded_value = html.unescape(value)
                    parsed_value = json.loads(decoded_value)
                    data_rows.append({
                        'Key': key,
                        'Time': int(time),
                        'ParsedValue': parsed_value,
                        'UpdateTime': int(update_time)
                    })
                except:
                    pass
        
        return pd.DataFrame(data_rows)
    
    def create_time_windows(self, window_hours: int = 24) -> List[Dict]:
        """Aggregate data into time windows for analysis"""
        window_seconds = window_hours * 3600
        
        # Get time range
        min_time = self.fitness_data['Time'].min()
        max_time = self.fitness_data['Time'].max()
        
        windows = []
        current_time = min_time
        
        while current_time < max_time:
            window_end = current_time + window_seconds
            window_data = self.fitness_data[
                (self.fitness_data['Time'] >= current_time) & 
                (self.fitness_data['Time'] < window_end)
            ]
            
            if len(window_data) > 0:
                windows.append(self._aggregate_window(window_data, current_time))
            
            current_time = window_end
        
        return windows
    
    def _aggregate_window(self, window_data: pd.DataFrame, start_time: int) -> Dict:
        """Aggregate metrics for a single time window"""
        agg = {
            'timestamp': start_time,
            'datetime': datetime.fromtimestamp(start_time).isoformat(),
            'calories': 0,
            'steps': 0,
            'distance': 0,
            'heart_rate_avg': 0,
            'heart_rate_max': 0,
            'heart_rate_min': 0,
            'heart_rate_readings': 0,
            'sleep_duration': 0,
            'active_minutes': 0
        }
        
        for _, row in window_data.iterrows():
            key = row['Key']
            value = row['ParsedValue']
            
            if key == 'calories':
                agg['calories'] += value.get('calories', 0)
            elif key == 'steps':
                agg['steps'] += value.get('steps', 0)
                agg['distance'] += value.get('distance', 0)
                agg['calories'] += value.get('calories', 0)
            elif key == 'heart_rate':
                bpm = value.get('bpm', 0)
                if bpm > 0:
                    if agg['heart_rate_readings'] == 0:
                        agg['heart_rate_min'] = bpm
                        agg['heart_rate_max'] = bpm
                        agg['heart_rate_avg'] = bpm
                    else:
                        agg['heart_rate_min'] = min(agg['heart_rate_min'], bpm)
                        agg['heart_rate_max'] = max(agg['heart_rate_max'], bpm)
                        agg['heart_rate_avg'] = (agg['heart_rate_avg'] * agg['heart_rate_readings'] + bpm) / (agg['heart_rate_readings'] + 1)
                    agg['heart_rate_readings'] += 1
            elif key == 'sleep':
                agg['sleep_duration'] += value.get('duration', 0)
        
        return agg
    
    def generate_text_summaries(self, windows: List[Dict]) -> List[Tuple[str, Dict]]:
        """Convert aggregated windows to natural language summaries"""
        summaries = []
        
        for window in windows:
            text = self._create_summary_text(window)
            summaries.append((text, window))
        
        return summaries
    
    def _create_summary_text(self, window: Dict) -> str:
        """Generate natural language summary for a time window"""
        dt = datetime.fromisoformat(window['datetime'])
        date_str = dt.strftime('%Y-%m-%d')
        
        parts = [f"Health summary for {date_str}:"]
        
        if window['steps'] > 0:
            parts.append(f"{window['steps']} steps covering {window['distance']} meters")
        
        if window['calories'] > 0:
            parts.append(f"{window['calories']} calories burned")
        
        if window['heart_rate_readings'] > 0:
            parts.append(f"heart rate averaged {window['heart_rate_avg']:.0f} bpm (range: {window['heart_rate_min']}-{window['heart_rate_max']})")
        
        if window['sleep_duration'] > 0:
            sleep_hours = window['sleep_duration'] / 60
            parts.append(f"{sleep_hours:.1f} hours of sleep")
        
        return ". ".join(parts) + "."

# Initialize processor
processor = HealthDataProcessor(
    'hlth_center_fitness_data.csv',
    'hlth_center_aggregated_fitness_data.csv',
    'hlth_center_sport_record.csv'
)

# Create time-based aggregations
windows = processor.create_time_windows(window_hours=24)
text_summaries = processor.generate_text_summaries(windows)

# Save processed data
processed_df = pd.DataFrame([
    {'text': text, **metrics} 
    for text, metrics in text_summaries
])
processed_df.to_csv('processed_health_data.csv', index=False)
print(f"Processed {len(text_summaries)} daily summaries")
