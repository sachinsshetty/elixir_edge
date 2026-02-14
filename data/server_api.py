from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import uvicorn

app = FastAPI(title="Health Data Analysis API")

# Load trained models
activity_classifier = MobileBERTHealthClassifier(num_classes=4)
activity_classifier.load_model('models/activity_classifier')

heart_classifier = MobileBERTHealthClassifier(num_classes=4)
heart_classifier.load_model('models/heart_health_classifier')

class HealthDataInput(BaseModel):
    steps: int
    distance: float
    calories: int
    heart_rate_avg: float
    heart_rate_max: int
    heart_rate_min: int
    sleep_duration: int  # minutes

class HealthAnalysisResponse(BaseModel):
    summary_text: str
    activity_level: str
    heart_health_status: str
    health_score: int
    recommendations: List[str]
    confidence_scores: Dict[str, float]

@app.post("/analyze", response_model=HealthAnalysisResponse)
async def analyze_health_data(data: HealthDataInput):
    """Analyze health metrics and return insights"""
    
    # Generate summary text
    processor = HealthDataProcessor.__new__(HealthDataProcessor)
    window = {
        'steps': data.steps,
        'distance': data.distance,
        'calories': data.calories,
        'heart_rate_avg': data.heart_rate_avg,
        'heart_rate_max': data.heart_rate_max,
        'heart_rate_min': data.heart_rate_min,
        'heart_rate_readings': 1 if data.heart_rate_avg > 0 else 0,
        'sleep_duration': data.sleep_duration,
        'datetime': datetime.now().isoformat()
    }
    
    summary_text = processor._create_summary_text(window)
    
    # Get predictions from models
    activity_pred = activity_classifier.predict([summary_text])[0]
    heart_pred = heart_classifier.predict([summary_text])[0]
    
    # Generate insights
    insights_gen = HealthInsightsGenerator()
    insights = insights_gen.generate_insights(window)
    
    return HealthAnalysisResponse(
        summary_text=summary_text,
        activity_level=insights['activity_level'],
        heart_health_status=insights['heart_health_status'],
        health_score=insights['health_score'],
        recommendations=insights['recommendations'],
        confidence_scores={
            'activity': float(activity_pred / 4),
            'heart_health': float(heart_pred / 4)
        }
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": "MobileBERT"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
