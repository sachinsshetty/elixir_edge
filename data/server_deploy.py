# deploy.py
import os
import subprocess
from pathlib import Path

def setup_environment():
    """Create project structure and install dependencies"""
    
    # Create directories
    dirs = ['models', 'data', 'logs', 'checkpoints']
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
    
    # Install requirements
    requirements = """
    torch>=2.0.0
    transformers>=4.30.0
    fastapi>=0.100.0
    uvicorn>=0.22.0
    pandas>=2.0.0
    numpy>=1.24.0
    scikit-learn>=1.3.0
    pydantic>=2.0.0
    """
    
    with open('requirements.txt', 'w') as f:
        f.write(requirements)
    
    subprocess.run(['pip', 'install', '-r', 'requirements.txt'])

def train_all_models():
    """Train all classification models"""
    df = pd.read_csv('data/health_data_with_labels.csv')
    
    tasks = [
        ('activity_level', 4),
        ('heart_health_status', 4),
        ('sleep_quality', 4)
    ]
    
    for task_name, num_classes in tasks:
        print(f"\n{'='*50}")
        print(f"Training {task_name} classifier")
        print(f"{'='*50}")
        
        classifier = MobileBERTHealthClassifier(num_classes=num_classes)
        train_loader, val_loader, label_encoder = classifier.prepare_data(
            df, 
            text_col='text', 
            label_col=task_name,
            batch_size=8
        )
        
        classifier.train(train_loader, val_loader, epochs=5)
        classifier.save_model(f'models/{task_name}_classifier')
        
        # Save label encoder
        import joblib
        joblib.dump(label_encoder, f'models/{task_name}_encoder.pkl')

if __name__ == "__main__":
    setup_environment()
    train_all_models()
    print("\nDeployment complete! Run: uvicorn main:app --reload")
