import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    MobileBertTokenizer,
    MobileBertForSequenceClassification,
    MobileBertForTokenClassification,
    AdamW,
    get_linear_schedule_with_warmup
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import numpy as np

class HealthTextDataset(Dataset):
    """PyTorch Dataset for health text summaries"""
    
    def __init__(self, texts, labels, tokenizer, max_length=128):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = self.labels[idx]
        
        encoding = self.tokenizer(
            text,
            add_special_tokens=True,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }

class MobileBERTHealthClassifier:
    """MobileBERT classifier for health data analysis"""
    
    def __init__(self, num_classes: int, model_name: str = 'google/mobilebert-uncased'):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.tokenizer = MobileBertTokenizer.from_pretrained(model_name)
        self.model = MobileBertForSequenceClassification.from_pretrained(
            model_name,
            num_labels=num_classes
        )
        self.model.to(self.device)
        self.num_classes = num_classes
    
    def prepare_data(self, df: pd.DataFrame, text_col: str, label_col: str,
                     test_size: float = 0.2, batch_size: int = 16):
        """Prepare train and validation dataloaders"""
        
        # Encode labels
        label_encoder = LabelEncoder()
        encoded_labels = label_encoder.fit_transform(df[label_col])
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            df[text_col].values,
            encoded_labels,
            test_size=test_size,
            random_state=42,
            stratify=encoded_labels
        )
        
        # Create datasets
        train_dataset = HealthTextDataset(X_train, y_train, self.tokenizer)
        val_dataset = HealthTextDataset(X_val, y_val, self.tokenizer)
        
        # Create dataloaders
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size)
        
        return train_loader, val_loader, label_encoder
    
    def train(self, train_loader, val_loader, epochs: int = 3, learning_rate: float = 2e-5):
        """Train the model"""
        
        optimizer = AdamW(self.model.parameters(), lr=learning_rate)
        total_steps = len(train_loader) * epochs
        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=0,
            num_training_steps=total_steps
        )
        
        best_val_acc = 0
        
        for epoch in range(epochs):
            print(f'\nEpoch {epoch + 1}/{epochs}')
            
            # Training
            self.model.train()
            train_loss = 0
            train_correct = 0
            train_total = 0
            
            for batch in train_loader:
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                labels = batch['labels'].to(self.device)
                
                optimizer.zero_grad()
                
                outputs = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels
                )
                
                loss = outputs.loss
                logits = outputs.logits
                
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                
                train_loss += loss.item()
                predictions = torch.argmax(logits, dim=1)
                train_correct += (predictions == labels).sum().item()
                train_total += labels.size(0)
            
            train_acc = train_correct / train_total
            avg_train_loss = train_loss / len(train_loader)
            
            # Validation
            val_acc, val_loss = self.evaluate(val_loader)
            
            print(f'Train Loss: {avg_train_loss:.4f}, Train Acc: {train_acc:.4f}')
            print(f'Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}')
            
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                self.save_model('best_health_model')
                print(f'Model saved! (val_acc: {val_acc:.4f})')
    
    def evaluate(self, dataloader):
        """Evaluate the model"""
        self.model.eval()
        total_loss = 0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for batch in dataloader:
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                labels = batch['labels'].to(self.device)
                
                outputs = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels
                )
                
                loss = outputs.loss
                logits = outputs.logits
                
                total_loss += loss.item()
                predictions = torch.argmax(logits, dim=1)
                correct += (predictions == labels).sum().item()
                total += labels.size(0)
        
        accuracy = correct / total
        avg_loss = total_loss / len(dataloader)
        
        return accuracy, avg_loss
    
    def predict(self, texts: List[str]) -> np.ndarray:
        """Make predictions on new texts"""
        self.model.eval()
        predictions = []
        
        with torch.no_grad():
            for text in texts:
                encoding = self.tokenizer(
                    text,
                    add_special_tokens=True,
                    max_length=128,
                    padding='max_length',
                    truncation=True,
                    return_tensors='pt'
                )
                
                input_ids = encoding['input_ids'].to(self.device)
                attention_mask = encoding['attention_mask'].to(self.device)
                
                outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
                logits = outputs.logits
                pred = torch.argmax(logits, dim=1).cpu().numpy()[0]
                predictions.append(pred)
        
        return np.array(predictions)
    
    def save_model(self, path: str):
        """Save model and tokenizer"""
        self.model.save_pretrained(path)
        self.tokenizer.save_pretrained(path)
    
    def load_model(self, path: str):
        """Load model and tokenizer"""
        self.model = MobileBertForSequenceClassification.from_pretrained(path)
        self.tokenizer = MobileBertTokenizer.from_pretrained(path)
        self.model.to(self.device)

# Example usage: Train activity level classifier
df = pd.read_csv('health_data_with_labels.csv')

classifier = MobileBERTHealthClassifier(num_classes=4)  # 4 activity levels
train_loader, val_loader, label_encoder = classifier.prepare_data(
    df, 
    text_col='text', 
    label_col='activity_level',
    batch_size=8
)

classifier.train(train_loader, val_loader, epochs=5)
