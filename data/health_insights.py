class HealthInsightsGenerator:
    """Generate health insights and recommendations as labels"""
    
    def __init__(self, min_steps: int = 7000, ideal_sleep_hours: float = 7.5):
        self.min_steps = min_steps
        self.ideal_sleep_hours = ideal_sleep_hours
    
    def generate_insights(self, window: Dict) -> Dict[str, any]:
        """Generate health insights and classification labels"""
        insights = {
            'activity_level': self._classify_activity(window),
            'heart_health_status': self._assess_heart_health(window),
            'sleep_quality': self._assess_sleep(window),
            'recommendations': self._generate_recommendations(window),
            'health_score': 0
        }
        
        # Calculate overall health score (0-100)
        score_components = []
        
        if window['steps'] > 0:
            step_score = min(100, (window['steps'] / 10000) * 100)
            score_components.append(step_score)
        
        if window['sleep_duration'] > 0:
            sleep_hours = window['sleep_duration'] / 60
            sleep_score = max(0, 100 - abs(sleep_hours - self.ideal_sleep_hours) * 20)
            score_components.append(sleep_score)
        
        if window['heart_rate_readings'] > 0:
            hr_score = self._calculate_hr_score(window)
            score_components.append(hr_score)
        
        if score_components:
            insights['health_score'] = int(np.mean(score_components))
        
        return insights
    
    def _classify_activity(self, window: Dict) -> str:
        """Classify activity level"""
        steps = window['steps']
        if steps < 3000:
            return 'sedentary'
        elif steps < 7000:
            return 'lightly_active'
        elif steps < 10000:
            return 'moderately_active'
        else:
            return 'highly_active'
    
    def _assess_heart_health(self, window: Dict) -> str:
        """Assess heart health based on resting heart rate"""
        if window['heart_rate_readings'] == 0:
            return 'no_data'
        
        avg_hr = window['heart_rate_avg']
        if avg_hr < 60:
            return 'excellent'
        elif avg_hr < 70:
            return 'good'
        elif avg_hr < 80:
            return 'average'
        else:
            return 'needs_attention'
    
    def _assess_sleep(self, window: Dict) -> str:
        """Assess sleep quality"""
        if window['sleep_duration'] == 0:
            return 'no_data'
        
        sleep_hours = window['sleep_duration'] / 60
        if sleep_hours < 6:
            return 'insufficient'
        elif sleep_hours < 7:
            return 'fair'
        elif sleep_hours < 9:
            return 'good'
        else:
            return 'excessive'
    
    def _generate_recommendations(self, window: Dict) -> List[str]:
        """Generate actionable recommendations"""
        recs = []
        
        if window['steps'] < 7000:
            recs.append("Increase daily step count to at least 7000 steps")
        
        if window['sleep_duration'] > 0:
            sleep_hours = window['sleep_duration'] / 60
            if sleep_hours < 7:
                recs.append("Aim for 7-9 hours of sleep per night")
        
        if window['heart_rate_avg'] > 75:
            recs.append("Consider stress reduction techniques and regular cardio exercise")
        
        if window['calories'] < 200:
            recs.append("Increase daily physical activity to boost metabolism")
        
        return recs
    
    def _calculate_hr_score(self, window: Dict) -> float:
        """Calculate heart rate health score"""
        avg_hr = window['heart_rate_avg']
        if avg_hr < 60:
            return 100
        elif avg_hr < 70:
            return 90
        elif avg_hr < 80:
            return 70
        else:
            return max(0, 100 - (avg_hr - 60) * 2)

# Generate insights for each window
insights_gen = HealthInsightsGenerator()
enhanced_data = []

for text, window in text_summaries:
    insights = insights_gen.generate_insights(window)
    enhanced_data.append({
        'text': text,
        'activity_level': insights['activity_level'],
        'heart_health_status': insights['heart_health_status'],
        'sleep_quality': insights['sleep_quality'],
        'health_score': insights['health_score'],
        'recommendations': '; '.join(insights['recommendations'])
    })

enhanced_df = pd.DataFrame(enhanced_data)
enhanced_df.to_csv('health_data_with_labels.csv', index=False)
