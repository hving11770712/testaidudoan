import math
import random
from collections import defaultdict

class UltraDicePredictionSystem:
    def __init__(self):
        self.history = []
        self.models = {}
        self.weights = {}
        self.performance = {}
        self.pattern_database = {}
        self.advanced_patterns = {}
        self.session_stats = {
            'streaks': {'T': 0, 'X': 0, 'maxT': 0, 'maxX': 0},
            'transitions': {'TtoT': 0, 'TtoX': 0, 'XtoT': 0, 'XtoX': 0},
            'volatility': 0.5,
            'pattern_confidence': {},
            'recent_accuracy': 0,
            'bias': {'T': 0, 'X': 0}
        }
        self.market_state = {
            'trend': 'neutral',
            'momentum': 0,
            'stability': 0.5,
            'regime': 'normal'
        }
        self.adaptive_parameters = {
            'pattern_min_length': 3,
            'pattern_max_length': 8,
            'volatility_threshold': 0.7,
            'trend_strength_threshold': 0.6,
            'pattern_confidence_decay': 0.95,
            'pattern_confidence_growth': 1.05
        }
        self.previous_top_models = None
        self.init_all_models()

    def init_all_models(self):
        for i in range(1, 22):
            # Model chính
            self.models[f'model{i}'] = getattr(self, f'model{i}')
            # Model mini
            self.models[f'model{i}Mini'] = getattr(self, f'model{i}Mini')
            # Model hỗ trợ
            self.models[f'model{i}Support1'] = getattr(self, f'model{i}Support1')
            self.models[f'model{i}Support2'] = getattr(self, f'model{i}Support2')
            
            # Khởi tạo trọng số và hiệu suất
            self.weights[f'model{i}'] = 1
            self.performance[f'model{i}'] = {
                'correct': 0,
                'total': 0,
                'recent_correct': 0,
                'recent_total': 0,
                'streak': 0,
                'max_streak': 0
            }
        
        self.init_pattern_database()
        self.init_advanced_patterns()
        self.init_support_models()

    def init_pattern_database(self):
        self.pattern_database = {
            '1-1': {'pattern': ['T', 'X', 'T', 'X'], 'probability': 0.7, 'strength': 0.8},
            '1-2-1': {'pattern': ['T', 'X', 'X', 'T'], 'probability': 0.65, 'strength': 0.75},
            '2-1-2': {'pattern': ['T', 'T', 'X', 'T', 'T'], 'probability': 0.68, 'strength': 0.78},
            '3-1': {'pattern': ['T', 'T', 'T', 'X'], 'probability': 0.72, 'strength': 0.82},
            '1-3': {'pattern': ['T', 'X', 'X', 'X'], 'probability': 0.72, 'strength': 0.82},
            '2-2': {'pattern': ['T', 'T', 'X', 'X'], 'probability': 0.66, 'strength': 0.76},
            '2-3': {'pattern': ['T', 'T', 'X', 'X', 'X'], 'probability': 0.71, 'strength': 0.81},
            '3-2': {'pattern': ['T', 'T', 'T', 'X', 'X'], 'probability': 0.73, 'strength': 0.83},
            '4-1': {'pattern': ['T', 'T', 'T', 'T', 'X'], 'probability': 0.76, 'strength': 0.86},
            '1-4': {'pattern': ['T', 'X', 'X', 'X', 'X'], 'probability': 0.76, 'strength': 0.86},
        }

    def init_advanced_patterns(self):
        self.advanced_patterns = {
            'dynamic-1': {
                'detect': lambda data: self.detect_dynamic_1(data),
                'predict': lambda data: 'X',
                'confidence': 0.72,
                'description': "4T trong 6 phiên, cuối là T -> dự đoán X"
            },
            'dynamic-2': {
                'detect': lambda data: self.detect_dynamic_2(data),
                'predict': lambda data: 'X',
                'confidence': 0.78,
                'description': "6+T trong 8 phiên, cuối là T -> dự đoán X mạnh"
            },
            'alternating-3': {
                'detect': lambda data: self.detect_alternating_3(data),
                'predict': lambda data: 'X' if data[-1] == 'T' else 'T',
                'confidence': 0.68,
                'description': "5 phiên đan xen hoàn hảo -> dự đoán đảo chiều"
            }
        }

    def detect_dynamic_1(self, data):
        if len(data) < 6:
            return False
        last_6 = data[-6:]
        return last_6.count('T') == 4 and last_6[-1] == 'T'

    def detect_dynamic_2(self, data):
        if len(data) < 8:
            return False
        last_8 = data[-8:]
        t_count = last_8.count('T')
        return t_count >= 6 and last_8[-1] == 'T'

    def detect_alternating_3(self, data):
        if len(data) < 5:
            return False
        last_5 = data[-5:]
        for i in range(1, len(last_5)):
            if last_5[i] == last_5[i-1]:
                return False
        return True

    def init_support_models(self):
        for i in range(1, 22):
            self.models[f'model{i}Support3'] = getattr(self, f'model{i}Support3', lambda: None)
            self.models[f'model{i}Support4'] = getattr(self, f'model{i}Support4', lambda: None)

    def arrays_equal(self, arr1, arr2):
        if len(arr1) != len(arr2):
            return False
        for i in range(len(arr1)):
            if arr1[i] != arr2[i]:
                return False
        return True

    def add_result(self, result):
        if self.history:
            last_result = self.history[-1]
            transition_key = f"{last_result}to{result}"
            self.session_stats['transitions'][transition_key] = self.session_stats['transitions'].get(transition_key, 0) + 1
            
            if result == last_result:
                self.session_stats['streaks'][result] += 1
                self.session_stats['streaks'][f'max{result}'] = max(
                    self.session_stats['streaks'][f'max{result}'],
                    self.session_stats['streaks'][result]
                )
            else:
                self.session_stats['streaks'][result] = 1
                self.session_stats['streaks'][last_result] = 0
        else:
            self.session_stats['streaks'][result] = 1
        
        self.history.append(result)
        if len(self.history) > 200:
            self.history.pop(0)
        
        self.update_volatility()
        self.update_pattern_confidence()
        self.update_market_state()
        self.update_pattern_database()

    def update_volatility(self):
        if len(self.history) < 10:
            return
        
        recent = self.history[-10:]
        changes = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i-1])
        self.session_stats['volatility'] = changes / (len(recent) - 1)

    def update_pattern_confidence(self):
        for pattern_name, confidence in self.session_stats['pattern_confidence'].items():
            if len(self.history) < 2:
                continue
            
            last_result = self.history[-1]
            
            if pattern_name in self.advanced_patterns:
                prediction = self.advanced_patterns[pattern_name]['predict'](self.history[:-1])
                if prediction != last_result:
                    self.session_stats['pattern_confidence'][pattern_name] = max(
                        0.1, confidence * self.adaptive_parameters['pattern_confidence_decay']
                    )
                else:
                    self.session_stats['pattern_confidence'][pattern_name] = min(
                        0.95, confidence * self.adaptive_parameters['pattern_confidence_growth']
                    )

    def update_market_state(self):
        if len(self.history) < 15:
            return
        
        recent = self.history[-15:]
        t_count = recent.count('T')
        x_count = recent.count('X')
        
        trend_strength = abs(t_count - x_count) / len(recent)
        
        if trend_strength > self.adaptive_parameters['trend_strength_threshold']:
            self.market_state['trend'] = 'up' if t_count > x_count else 'down'
        else:
            self.market_state['trend'] = 'neutral'
        
        momentum = 0
        for i in range(1, len(recent)):
            if recent[i] == recent[i-1]:
                momentum += 0.1 if recent[i] == 'T' else -0.1
        
        self.market_state['momentum'] = math.tanh(momentum)
        self.market_state['stability'] = 1 - self.session_stats['volatility']
        
        if self.session_stats['volatility'] > self.adaptive_parameters['volatility_threshold']:
            self.market_state['regime'] = 'volatile'
        elif trend_strength > 0.7:
            self.market_state['regime'] = 'trending'
        elif trend_strength < 0.3:
            self.market_state['regime'] = 'random'
        else:
            self.market_state['regime'] = 'normal'

    def update_pattern_database(self):
        if len(self.history) < 10:
            return
        
        for length in range(self.adaptive_parameters['pattern_min_length'], 
                           self.adaptive_parameters['pattern_max_length'] + 1):
            for i in range(len(self.history) - length + 1):
                segment = self.history[i:i + length]
                pattern_key = '-'.join(segment)
                
                if pattern_key not in self.pattern_database:
                    count = 0
                    for j in range(len(self.history) - length):
                        test_segment = self.history[j:j + length]
                        if '-'.join(test_segment) == pattern_key:
                            count += 1
                    
                    if count > 2:
                        probability = count / (len(self.history) - length)
                        strength = min(0.9, probability * 1.2)
                        
                        self.pattern_database[pattern_key] = {
                            'pattern': segment,
                            'probability': probability,
                            'strength': strength
                        }

    # MODEL 1: Nhận biết các loại cầu cơ bản
    def model1(self):
        recent = self.history[-10:] if len(self.history) >= 10 else self.history
        if len(recent) < 4:
            return None
        
        patterns = self.model1Mini(recent)
        if not patterns:
            return None
        
        best_pattern = max(patterns, key=lambda x: x['probability'])
        
        confidence = best_pattern['probability'] * 0.8
        if self.market_state['regime'] == 'trending':
            confidence *= 1.1
        elif self.market_state['regime'] == 'volatile':
            confidence *= 0.9
        
        return {
            'prediction': best_pattern['prediction'],
            'confidence': min(0.95, confidence),
            'reason': f"Phát hiện pattern {best_pattern['type']} (xác suất {best_pattern['probability']:.2f})"
        }

    def model1Mini(self, data):
        patterns = []
        
        for pattern_type, pattern_data in self.pattern_database.items():
            pattern = pattern_data['pattern']
            if len(data) < len(pattern):
                continue
            
            segment = data[-(len(pattern) - 1):]
            pattern_without_last = pattern[:-1]
            
            if segment == pattern_without_last:
                patterns.append({
                    'type': pattern_type,
                    'prediction': pattern[-1],
                    'probability': pattern_data['probability'],
                    'strength': pattern_data['strength']
                })
        
        return patterns

    def model1Support1(self):
        return {
            'status': "Phân tích pattern nâng cao",
            'total_patterns': len(self.pattern_database),
            'recent_patterns': len(self.pattern_database)
        }

    def model1Support2(self):
        pattern_count = len(self.pattern_database)
        avg_confidence = sum(p['probability'] for p in self.pattern_database.values()) / pattern_count if pattern_count > 0 else 0
        
        return {
            'status': "Đánh giá độ tin cậy pattern",
            'pattern_count': pattern_count,
            'average_confidence': avg_confidence
        }

    # MODEL 2: Bắt trend xu hướng ngắn và dài
    def model2(self):
        short_term = self.history[-5:] if len(self.history) >= 5 else self.history
        long_term = self.history[-20:] if len(self.history) >= 20 else self.history
        
        if len(short_term) < 3 or len(long_term) < 10:
            return None
        
        short_analysis = self.model2Mini(short_term)
        long_analysis = self.model2Mini(long_term)
        
        if short_analysis['trend'] == long_analysis['trend']:
            prediction = 'T' if short_analysis['trend'] == 'up' else 'X'
            confidence = (short_analysis['strength'] + long_analysis['strength']) / 2
            reason = f"Xu hướng ngắn và dài hạn cùng {short_analysis['trend']}"
        else:
            if short_analysis['strength'] > long_analysis['strength'] * 1.5:
                prediction = 'T' if short_analysis['trend'] == 'up' else 'X'
                confidence = short_analysis['strength']
                reason = "Xu hướng ngắn hạn mạnh hơn dài hạn"
            else:
                prediction = 'T' if long_analysis['trend'] == 'up' else 'X'
                confidence = long_analysis['strength']
                reason = "Xu hướng dài hạn ổn định hơn"
        
        if self.market_state['regime'] == 'trending':
            confidence *= 1.15
        elif self.market_state['regime'] == 'volatile':
            confidence *= 0.85
        
        return {
            'prediction': prediction,
            'confidence': min(0.95, confidence * 0.9),
            'reason': reason
        }

    def model2Mini(self, data):
        t_count = data.count('T')
        x_count = data.count('X')
        
        trend = 'up' if t_count > x_count else ('down' if x_count > t_count else 'neutral')
        strength = abs(t_count - x_count) / len(data)
        
        changes = sum(1 for i in range(1, len(data)) if data[i] != data[i-1])
        volatility = changes / (len(data) - 1) if len(data) > 1 else 0
        strength = strength * (1 - volatility / 2)
        
        return {'trend': trend, 'strength': strength, 'volatility': volatility}

    # MODEL 3: Xem trong 12 phiên gần nhất có sự chênh lệch cao thì sẽ dự đoán bên còn lại
    def model3(self):
        recent = self.history[-12:] if len(self.history) >= 12 else self.history
        if len(recent) < 12:
            return None
        
        analysis = self.model3Mini(recent)
        
        if analysis['difference'] < 0.4:
            return None
        
        confidence = analysis['difference'] * 0.8
        if self.market_state['regime'] == 'random':
            confidence *= 1.1
        elif self.market_state['regime'] == 'trending':
            confidence *= 0.9
        
        return {
            'prediction': analysis['prediction'],
            'confidence': min(0.95, confidence),
            'reason': f"Chênh lệch cao ({analysis['difference']*100:.0f}%) trong 12 phiên, dự đoán cân bằng"
        }

    def model3Mini(self, data):
        t_count = data.count('T')
        x_count = data.count('X')
        total = len(data)
        difference = abs(t_count - x_count) / total
        
        return {
            'difference': difference,
            'prediction': 'X' if t_count > x_count else 'T',
            't_count': t_count,
            'x_count': x_count
        }

    # Các model khác sẽ được triển khai tương tự...
    # Do giới hạn độ dài, tôi chỉ triển khai 3 model đầu tiên làm ví dụ

    def get_all_predictions(self):
        predictions = {}
        for i in range(1, 22):
            predictions[f'model{i}'] = self.models[f'model{i}']()
        return predictions

    def get_final_prediction(self):
        predictions = self.get_all_predictions()
        t_score = 0
        x_score = 0
        total_weight = 0
        reasons = []
        
        for model_name, prediction in predictions.items():
            if prediction and prediction.get('prediction'):
                weight = self.weights.get(model_name, 1)
                score = prediction['confidence'] * weight
                
                if prediction['prediction'] == 'T':
                    t_score += score
                elif prediction['prediction'] == 'X':
                    x_score += score
                
                total_weight += weight
                reasons.append(f"{model_name}: {prediction['reason']} ({prediction['confidence']:.2f})")
        
        if total_weight == 0:
            return None
        
        final_prediction = None
        final_confidence = 0
        
        if t_score > x_score:
            final_prediction = 'T'
            final_confidence = t_score / (t_score + x_score)
        elif x_score > t_score:
            final_prediction = 'X'
            final_confidence = x_score / (t_score + x_score)
        
        final_confidence = self.adjust_confidence_by_volatility(final_confidence)
        
        return {
            'prediction': final_prediction,
            'confidence': final_confidence,
            'reasons': reasons,
            'details': predictions,
            'session_stats': self.session_stats,
            'market_state': self.market_state
        }

    def adjust_confidence_by_volatility(self, confidence):
        if self.session_stats['volatility'] > 0.7:
            return confidence * 0.8
        if self.session_stats['volatility'] < 0.3:
            return min(0.95, confidence * 1.1)
        return confidence

    def update_performance(self, actual_result):
        predictions = self.get_all_predictions()
        
        for model_name, prediction in predictions.items():
            if prediction and prediction.get('prediction'):
                self.performance[model_name]['total'] += 1
                self.performance[model_name]['recent_total'] += 1
                
                if prediction['prediction'] == actual_result:
                    self.performance[model_name]['correct'] += 1
                    self.performance[model_name]['recent_correct'] += 1
                    self.performance[model_name]['streak'] += 1
                    self.performance[model_name]['max_streak'] = max(
                        self.performance[model_name]['max_streak'],
                        self.performance[model_name]['streak']
                    )
                else:
                    self.performance[model_name]['streak'] = 0
                
                if self.performance[model_name]['recent_total'] > 50:
                    self.performance[model_name]['recent_total'] -= 1
                    if (self.performance[model_name]['recent_correct'] > 0 and 
                        self.performance[model_name]['recent_correct'] / self.performance[model_name]['recent_total'] > 
                        self.performance[model_name]['correct'] / self.performance[model_name]['total']):
                        self.performance[model_name]['recent_correct'] -= 1
                
                accuracy = self.performance[model_name]['correct'] / self.performance[model_name]['total']
                self.weights[model_name] = max(0.1, min(2, accuracy * 2))
        
        total_predictions = sum(1 for p in predictions.values() if p and p.get('prediction'))
        correct_predictions = sum(1 for p in predictions.values() if p and p.get('prediction') == actual_result)
        self.session_stats['recent_accuracy'] = correct_predictions / total_predictions if total_predictions > 0 else 0
