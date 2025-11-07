import os
import json
import time
import logging
import threading
import requests
import random
import math
from collections import Counter
from flask import Flask, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_URL = "https://hithu-ddo6.onrender.com/api/hit"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
POLL_INTERVAL = 5
MAX_HISTORY_LEN = 500

app = Flask(__name__)
CORS(app)
app.history = []
app.session_ids = []
app.session_details = []
app.lock = threading.Lock()

# Thêm biến để lưu dự đoán phiên trước và kết quả so sánh
app.previous_predictions = {}  # Lưu dự đoán theo session_id
app.prediction_accuracy = {    # Thống kê độ chính xác
    'total_predictions': 0,
    'correct_predictions': 0,
    'accuracy_rate': 0.0
}

# ------------------------- LMC GAMING AI SYSTEM -------------------------
class LMCPredictionSystem:
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
        self.init_all_models()

    def init_all_models(self):
        """Khởi tạo tất cả models"""
        for i in range(1, 22):
            model_name = f'model{i}'
            self.models[model_name] = getattr(self, model_name, lambda: None)
            self.weights[model_name] = 1.0
            self.performance[model_name] = {
                'correct': 0,
                'total': 0,
                'recent_correct': 0,
                'recent_total': 0,
                'streak': 0,
                'max_streak': 0
            }
        
        self.init_pattern_database()
        self.init_advanced_patterns()

    def init_pattern_database(self):
        """Khởi tạo cơ sở dữ liệu pattern"""
        self.pattern_database = {
            'T-X-T-X': {'prediction': 'X', 'probability': 0.7, 'strength': 0.8},
            'X-T-X-T': {'prediction': 'T', 'probability': 0.7, 'strength': 0.8},
            'T-T-X-X': {'prediction': 'T', 'probability': 0.66, 'strength': 0.76},
            'X-X-T-T': {'prediction': 'X', 'probability': 0.66, 'strength': 0.76},
            'T-T-T-X': {'prediction': 'X', 'probability': 0.72, 'strength': 0.82},
            'X-X-X-T': {'prediction': 'T', 'probability': 0.72, 'strength': 0.82},
            'T-X-X-T': {'prediction': 'T', 'probability': 0.65, 'strength': 0.75},
            'X-T-T-X': {'prediction': 'X', 'probability': 0.65, 'strength': 0.75}
        }

    def init_advanced_patterns(self):
        """Khởi tạo pattern nâng cao"""
        self.advanced_patterns = {
            'dynamic_1': {
                'detect': lambda data: len(data) >= 6 and 
                    data[-6:].count('T') == 4 and data[-1] == 'T',
                'predict': lambda data: 'X',
                'confidence': 0.72,
                'description': "4T trong 6 phiên, cuối là T -> dự đoán X"
            },
            'dynamic_2': {
                'detect': lambda data: len(data) >= 8 and 
                    data[-8:].count('T') >= 6 and data[-1] == 'T',
                'predict': lambda data: 'X',
                'confidence': 0.78,
                'description': "6+T trong 8 phiên, cuối là T -> dự đoán X mạnh"
            },
            'alternating_3': {
                'detect': lambda data: len(data) >= 5 and 
                    all(data[i] != data[i-1] for i in range(-4, 0)),
                'predict': lambda data: 'X' if data[-1] == 'T' else 'T',
                'confidence': 0.68,
                'description': "5 phiên đan xen hoàn hảo -> dự đoán đảo chiều"
            }
        }

    def add_result(self, result):
        """Thêm kết quả mới và cập nhật thống kê"""
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
        """Cập nhật độ biến động"""
        if len(self.history) < 10:
            return
        
        recent = self.history[-10:]
        changes = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i-1])
        self.session_stats['volatility'] = changes / (len(recent) - 1)

    def update_pattern_confidence(self):
        """Cập nhật độ tin cậy pattern"""
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
        """Cập nhật trạng thái thị trường"""
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
        
        # Tính momentum
        momentum = 0
        for i in range(1, len(recent)):
            if recent[i] == recent[i-1]:
                momentum += 0.1 if recent[i] == 'T' else -0.1
        self.market_state['momentum'] = math.tanh(momentum)
        
        self.market_state['stability'] = 1 - self.session_stats['volatility']
        
        # Xác định regime
        if self.session_stats['volatility'] > self.adaptive_parameters['volatility_threshold']:
            self.market_state['regime'] = 'volatile'
        elif trend_strength > 0.7:
            self.market_state['regime'] = 'trending'
        elif trend_strength < 0.3:
            self.market_state['regime'] = 'random'
        else:
            self.market_state['regime'] = 'normal'

    def update_pattern_database(self):
        """Cập nhật cơ sở dữ liệu pattern"""
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
        if len(self.history) < 4:
            return None
        
        recent = self.history[-10:]
        patterns = []
        
        for pattern_key, pattern_data in self.pattern_database.items():
            pattern = pattern_data['pattern']
            if len(recent) < len(pattern) - 1:
                continue
            
            segment = recent[-(len(pattern)-1):]
            pattern_without_last = pattern[:-1]
            
            if segment == pattern_without_last:
                patterns.append({
                    'type': pattern_key,
                    'prediction': pattern[-1],
                    'probability': pattern_data['probability'],
                    'strength': pattern_data['strength']
                })
        
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
            'reason': f"[Model1] Pattern {best_pattern['type']} (xác suất {best_pattern['probability']:.2f})"
        }

    # MODEL 2: Bắt trend xu hướng ngắn và dài
    def model2(self):
        short_term = self.history[-5:] if len(self.history) >= 5 else []
        long_term = self.history[-20:] if len(self.history) >= 20 else []
        
        if not short_term or not long_term:
            return None
        
        def analyze_trend(data):
            t_count = data.count('T')
            x_count = data.count('X')
            trend = 'up' if t_count > x_count else 'down' if x_count > t_count else 'neutral'
            strength = abs(t_count - x_count) / len(data)
            
            changes = sum(1 for i in range(1, len(data)) if data[i] != data[i-1])
            volatility = changes / (len(data) - 1)
            strength = strength * (1 - volatility / 2)
            
            return {'trend': trend, 'strength': strength, 'volatility': volatility}
        
        short_analysis = analyze_trend(short_term)
        long_analysis = analyze_trend(long_term)
        
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
            'reason': f"[Model2] {reason}"
        }

    # MODEL 3: Mean reversion trong 12 phiên
    def model3(self):
        if len(self.history) < 12:
            return None
        
        recent = self.history[-12:]
        t_count = recent.count('T')
        x_count = recent.count('X')
        total = len(recent)
        difference = abs(t_count - x_count) / total
        
        if difference < 0.4:
            return None
        
        prediction = 'X' if t_count > x_count else 'T'
        confidence = difference * 0.8
        
        if self.market_state['regime'] == 'random':
            confidence *= 1.1
        elif self.market_state['regime'] == 'trending':
            confidence *= 0.9
        
        return {
            'prediction': prediction,
            'confidence': min(0.95, confidence),
            'reason': f"[Model3] Chênh lệch cao ({difference*100:.0f}%) trong 12 phiên, dự đoán cân bằng"
        }

    # MODEL 4: Bắt cầu ngắn hạn
    def model4(self):
        if len(self.history) < 4:
            return None
        
        recent = self.history[-6:]
        last_3 = recent[-3:] if len(recent) >= 3 else recent
        
        t_count = last_3.count('T')
        x_count = last_3.count('X')
        
        if t_count == 3:
            prediction, confidence, trend = 'T', 0.7, 'Tăng mạnh'
        elif x_count == 3:
            prediction, confidence, trend = 'X', 0.7, 'Giảm mạnh'
        elif t_count == 2:
            prediction, confidence, trend = 'T', 0.65, 'Tăng nhẹ'
        elif x_count == 2:
            prediction, confidence, trend = 'X', 0.65, 'Giảm nhẹ'
        else:
            changes = sum(1 for i in range(1, len(recent[-4:])) if recent[-4:][i] != recent[-4:][i-1])
            if changes >= 3:
                prediction = 'X' if recent[-1] == 'T' else 'T'
                confidence, trend = 0.6, 'Đảo chiều'
            else:
                prediction = recent[-1]
                confidence, trend = 0.55, 'Ổn định'
        
        if self.market_state['regime'] == 'trending':
            confidence *= 1.1
        elif self.market_state['regime'] == 'volatile':
            confidence *= 0.9
        
        return {
            'prediction': prediction,
            'confidence': min(0.95, confidence),
            'reason': f"[Model4] Cầu ngắn hạn {trend}"
        }

    # MODEL 5: Cân bằng tỷ lệ model
    def model5(self):
        predictions = self.get_all_predictions()
        t_predictions = sum(1 for p in predictions.values() if p and p['prediction'] == 'T')
        x_predictions = sum(1 for p in predictions.values() if p and p['prediction'] == 'X')
        total = t_predictions + x_predictions
        
        if total < 5:
            return None
        
        difference = abs(t_predictions - x_predictions) / total
        
        if difference > 0.6:
            prediction = 'X' if t_predictions > x_predictions else 'T'
            return {
                'prediction': prediction,
                'confidence': difference * 0.9,
                'reason': f"[Model5] Cân bằng tỷ lệ chênh lệch cao ({difference*100:.0f}%)"
            }
        
        return None

    # MODEL 6: Quyết định bắt theo cầu hay bẻ cầu
    def model6(self):
        trend_analysis = self.model2()
        if not trend_analysis:
            return None
        
        continuity = self.analyze_continuity(self.history[-8:] if len(self.history) >= 8 else self.history)
        break_probability = self.calculate_break_probability(self.history)
        
        if continuity['streak'] >= 5 and break_probability > 0.7:
            prediction = 'X' if trend_analysis['prediction'] == 'T' else 'T'
            return {
                'prediction': prediction,
                'confidence': break_probability * 0.8,
                'reason': f"[Model6] Cầu liên tục {continuity['streak']} lần, xác suất bẻ cầu {break_probability:.2f}"
            }
        
        return {
            'prediction': trend_analysis['prediction'],
            'confidence': trend_analysis['confidence'] * 0.9,
            'reason': "[Model6] Tiếp tục theo xu hướng"
        }

    def analyze_continuity(self, data):
        if len(data) < 2:
            return {'streak': 0, 'direction': 'neutral', 'max_streak': 0}
        
        current_streak = 1
        max_streak = 1
        direction = data[-1]
        
        for i in range(len(data)-1, 0, -1):
            if data[i] == data[i-1]:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                break
        
        return {'streak': current_streak, 'direction': direction, 'max_streak': max_streak}

    def calculate_break_probability(self, data):
        if len(data) < 20:
            return 0.5
        
        break_count = 0
        total_opportunities = 0
        
        for i in range(5, len(data)):
            segment = data[i-5:i]
            streak = self.analyze_continuity(segment)['streak']
            
            if streak >= 4:
                total_opportunities += 1
                if data[i] != segment[-1]:
                    break_count += 1
        
        return break_count / total_opportunities if total_opportunities > 0 else 0.5

    # MODEL 7-21: Các model còn lại (simplified)
    def model7(self):
        """Cân bằng trọng số model"""
        return None  # Implement later

    def model8(self):
        """Nhận biết cầu xấu"""
        if len(self.history) < 10:
            return None
        
        randomness = self.calculate_randomness(self.history[-15:])
        if randomness > 0.7:
            return {
                'prediction': 'T' if random.random() > 0.5 else 'X',
                'confidence': 0.5,
                'reason': f"[Model8] Phát hiện cầu xấu (độ ngẫu nhiên {randomness:.2f})"
            }
        return None

    def calculate_randomness(self, data):
        if len(data) < 10:
            return 0
        
        changes = sum(1 for i in range(1, len(data)) if data[i] != data[i-1])
        change_ratio = changes / (len(data) - 1)
        
        t_count = data.count('T')
        x_count = data.count('X')
        distribution = abs(t_count - x_count) / len(data)
        
        p_t = t_count / len(data)
        p_x = x_count / len(data)
        entropy = 0
        if p_t > 0:
            entropy -= p_t * math.log2(p_t)
        if p_x > 0:
            entropy -= p_x * math.log2(p_x)
        
        return change_ratio * 0.4 + (1 - distribution) * 0.3 + entropy * 0.3

    # Các model 9-21 sẽ được triển khai tương tự
    def model9(self): return self.model1()  # Pattern nâng cao
    def model10(self): return self.model6()  # Xác suất bẻ cầu
    def model11(self): return self.model8()  # Phân tích biến động
    def model12(self): return self.model4()  # Pattern ngắn
    def model13(self): return self.analyze_performance()  # Đánh giá hiệu suất
    def model14(self): return self.model6()  # Xác suất bẻ cầu xu hướng
    def model15(self): return self.model6()  # Quyết định theo/bẻ xu hướng
    def model16(self): return self.model10()  # Xác suất bẻ tổng hợp
    def model17(self): return self.model7()  # Cân bằng trọng số nâng cao
    def model18(self): return self.model2()  # Xu hướng ngắn hạn
    def model19(self): return self.model1()  # Xu hướng phổ biến
    def model20(self): return self.ensemble_prediction()  # Max Performance
    def model21(self): return self.model5()  # Cân bằng tổng thể

    def analyze_performance(self):
        """Model 13: Đánh giá hiệu suất"""
        performance_stats = {}
        for model_name, perf in self.performance.items():
            if perf['total'] > 0:
                performance_stats[model_name] = {
                    'accuracy': perf['correct'] / perf['total'],
                    'recent_accuracy': perf['recent_correct'] / perf['recent_total'] if perf['recent_total'] > 0 else 0,
                    'total': perf['total'],
                    'streak': perf['streak']
                }
        
        best_model = max(performance_stats.items(), key=lambda x: x[1]['accuracy'], default=(None, {'accuracy': 0}))
        
        if best_model[0]:
            return {
                'prediction': None,
                'confidence': best_model[1]['accuracy'],
                'reason': f"[Model13] Model hiệu suất cao nhất: {best_model[0]} ({best_model[1]['accuracy']:.2f})"
            }
        return None

    def ensemble_prediction(self):
        """Model 20: Kết hợp model hiệu suất cao"""
        performance_stats = {}
        for model_name, perf in self.performance.items():
            if perf['total'] > 10:
                performance_stats[model_name] = perf['correct'] / perf['total']
        
        if not performance_stats:
            return None
        
        best_models = sorted(performance_stats.items(), key=lambda x: x[1], reverse=True)[:3]
        
        t_score = 0
        x_score = 0
        
        for model_name, accuracy in best_models:
            prediction = self.models[model_name]()
            if prediction and prediction['prediction']:
                weight = accuracy
                if prediction['prediction'] == 'T':
                    t_score += weight * prediction['confidence']
                else:
                    x_score += weight * prediction['confidence']
        
        total_score = t_score + x_score
        if total_score == 0:
            return None
        
        return {
            'prediction': 'T' if t_score > x_score else 'X',
            'confidence': max(t_score, x_score) / total_score,
            'reason': f"[Model20] Kết hợp {len(best_models)} model hiệu suất cao"
        }

    def get_all_predictions(self):
        """Lấy tất cả dự đoán từ các model"""
        predictions = {}
        for i in range(1, 22):
            model_name = f'model{i}'
            predictions[model_name] = self.models[model_name]()
        return predictions

    def get_final_prediction(self):
        """Lấy dự đoán cuối cùng kết hợp tất cả model"""
        predictions = self.get_all_predictions()
        
        t_score = 0
        x_score = 0
        total_weight = 0
        reasons = []
        
        for model_name, prediction in predictions.items():
            if prediction and prediction['prediction']:
                weight = self.weights.get(model_name, 1.0)
                score = prediction['confidence'] * weight
                
                if prediction['prediction'] == 'T':
                    t_score += score
                else:
                    x_score += score
                
                total_weight += weight
                reasons.append(f"{model_name}: {prediction['reason']}")
        
        if total_weight == 0:
            return None
        
        final_prediction = 'T' if t_score > x_score else 'X'
        final_confidence = max(t_score, x_score) / (t_score + x_score)
        
        # Điều chỉnh confidence theo độ biến động
        if self.session_stats['volatility'] > 0.7:
            final_confidence *= 0.8
        elif self.session_stats['volatility'] < 0.3:
            final_confidence = min(0.95, final_confidence * 1.1)
        
        return {
            'prediction': final_prediction,
            'confidence': final_confidence,
            'reason': ' | '.join(reasons[:2]),  # Chỉ lấy 2 lý do đầu
            'details': predictions,
            'session_stats': self.session_stats,
            'market_state': self.market_state
        }

    def update_performance(self, actual_result):
        """Cập nhật hiệu suất các model"""
        predictions = self.get_all_predictions()
        
        for model_name, prediction in predictions.items():
            if prediction and prediction['prediction']:
                perf = self.performance[model_name]
                perf['total'] += 1
                perf['recent_total'] += 1
                
                if prediction['prediction'] == actual_result:
                    perf['correct'] += 1
                    perf['recent_correct'] += 1
                    perf['streak'] += 1
                    perf['max_streak'] = max(perf['max_streak'], perf['streak'])
                else:
                    perf['streak'] = 0
                
                # Giữ recent stats trong phạm vi 50
                if perf['recent_total'] > 50:
                    perf['recent_total'] -= 1
                    if (perf['recent_correct'] > 0 and 
                        perf['recent_correct'] / perf['recent_total'] > 
                        perf['correct'] / perf['total']):
                        perf['recent_correct'] -= 1
                
                # Cập nhật trọng số
                accuracy = perf['correct'] / perf['total'] if perf['total'] > 0 else 0
                self.weights[model_name] = max(0.1, min(2.0, accuracy * 2))

# Khởi tạo hệ thống LMC Gaming AI
lmc_system = LMCPredictionSystem()

# ------------------------- PATTERN DATA -------------------------
PATTERN_DATA = {
    # Giữ nguyên pattern data từ trước
    "tttt": {"tai": 73, "xiu": 27}, "xxxx": {"tai": 27, "xiu": 73},
    "tttttt": {"tai": 83, "xiu": 17}, "xxxxxx": {"tai": 17, "xiu": 83},
    "ttttx": {"tai": 40, "xiu": 60}, "xxxxt": {"tai": 60, "xiu": 40},
    "ttttttx": {"tai": 30, "xiu": 70}, "xxxxxxt": {"tai": 70, "xiu": 30},
    "ttxx": {"tai": 62, "xiu": 38}, "xxtt": {"tai": 38, "xiu": 62},
    "ttxxtt": {"tai": 32, "xiu": 68}, "xxttxx": {"tai": 68, "xiu": 32},
    "txx": {"tai": 60, "xiu": 40}, "xtt": {"tai": 40, "xiu": 60},
    "txxtx": {"tai": 63, "xiu": 37}, "xttxt": {"tai": 37, "xiu": 63},
    "tttxt": {"tai": 60, "xiu": 40}, "xxxtx": {"tai": 40, "xiu": 60},
    "tttxx": {"tai": 60, "xiu": 40}, "xxxtt": {"tai": 40, "xiu": 60},
    "txxt": {"tai": 60, "xiu": 40}, "xttx": {"tai": 40, "xiu": 60},
    "ttxxttx": {"tai": 30, "xiu": 70}, "xxttxxt": {"tai": 70, "xiu": 30},
    "tttttttt": {"tai": 88, "xiu": 12}, "xxxxxxxx": {"tai": 12, "xiu": 88},
    "tttttttx": {"tai": 25, "xiu": 75}, "xxxxxxxxt": {"tai": 75, "xiu": 25},
    "tttttxxx": {"tai": 35, "xiu": 65}, "xxxxtttt": {"tai": 65, "xiu": 35},
    "ttttxxxx": {"tai": 30, "xiu": 70}, "xxxxtttx": {"tai": 70, "xiu": 30},
    "txtxtx": {"tai": 68, "xiu": 32}, "xtxtxt": {"tai": 32, "xiu": 68},
    "ttxtxt": {"tai": 55, "xiu": 45}, "xxtxtx": {"tai": 45, "xiu": 55},
    "txtxxt": {"tai": 60, "xiu": 40}, "xtxttx": {"tai": 40, "xiu": 60},
    "ttx": {"tai": 65, "xiu": 35}, "xxt": {"tai": 35, "xiu": 65},
    "txt": {"tai": 58, "xiu": 42}, "xtx": {"tai": 42, "xiu": 58},
    "tttx": {"tai": 70, "xiu": 30}, "xxxt": {"tai": 30, "xiu": 70},
    "ttxt": {"tai": 63, "xiu": 37}, "xxtx": {"tai": 37, "xiu": 63},
    "txxx": {"tai": 25, "xiu": 75}, "xttt": {"tai": 75, "xiu": 25},
    "tttxx": {"tai": 60, "xiu": 40}, "xxxtt": {"tai": 40, "xiu": 60},
    "ttxtx": {"tai": 62, "xiu": 38}, "xxtxt": {"tai": 38, "xiu": 62},
    "ttxxt": {"tai": 55, "xiu": 45}, "xxttx": {"tai": 45, "xiu": 55},
    "ttttx": {"tai": 40, "xiu": 60}, "xxxxt": {"tai": 60, "xiu": 40},
    "tttttx": {"tai": 30, "xiu": 70}, "xxxxxt": {"tai": 70, "xiu": 30},
    "ttttttx": {"tai": 25, "xiu": 75}, "xxxxxxt": {"tai": 75, "xiu": 25},
    "tttttttx": {"tai": 20, "xiu": 80}, "xxxxxxxt": {"tai": 80, "xiu": 20},
    "ttttttttx": {"tai": 15, "xiu": 85}, "xxxxxxxxt": {"tai": 85, "xiu": 15},
    "txtx": {"tai": 52, "xiu": 48}, "xtxt": {"tai": 48, "xiu": 52},
    "txtxt": {"tai": 53, "xiu": 47}, "xtxtx": {"tai": 47, "xiu": 53},
    "txtxtx": {"tai": 55, "xiu": 45}, "xtxtxt": {"tai": 45, "xiu": 55},
    "txtxtxt": {"tai": 57, "xiu": 43}, "xtxtxtx": {"tai": 43, "xiu": 57},
    "ttxxttxx": {"tai": 38, "xiu": 62}, "xxttxxtt": {"tai": 62, "xiu": 38},
    "ttxxxttx": {"tai": 45, "xiu": 55}, "xxttxxxt": {"tai": 55, "xiu": 45},
    "ttxtxttx": {"tai": 50, "xiu": 50}, "xxtxtxxt": {"tai": 50, "xiu": 50},
    "ttxttx": {"tai": 60, "xiu": 40}, "xxtxxt": {"tai": 40, "xiu": 60},
    "ttxxtx": {"tai": 58, "xiu": 42}, "xxtxxt": {"tai": 42, "xiu": 58},
    "ttxtxtx": {"tai": 62, "xiu": 38}, "xxtxtxt": {"tai": 38, "xiu": 62},
    "ttxxtxt": {"tai": 55, "xiu": 45}, "xxtxttx": {"tai": 45, "xiu": 55},
    "ttxtxxt": {"tai": 65, "xiu": 35}, "xxtxttx": {"tai": 35, "xiu": 65},
    "ttxtxttx": {"tai": 70, "xiu": 30}, "xxtxtxxt": {"tai": 30, "xiu": 70},
    "ttxxtxtx": {"tai": 68, "xiu": 32}, "xxtxtxtx": {"tai": 32, "xiu": 68},
    "ttxtxxtx": {"tai": 72, "xiu": 28}, "xxtxtxxt": {"tai": 28, "xiu": 72},
    "ttxxtxxt": {"tai": 75, "xiu": 25}, "xxtxtxxt": {"tai": 25, "xiu": 75},
}

# ------------------------- PREDICTION FUNCTIONS -------------------------
def find_closest_pattern(pattern_str):
    for key in sorted(PATTERN_DATA.keys(), key=len, reverse=True):
        if pattern_str.endswith(key):
            return key
    return None

def pattern_predict(session_details):
    if not session_details:
        return {"prediction": "Tài", "confidence": 0.5, "reason": "[Pattern] Thiếu dữ liệu"}

    elements = ["t" if s["result"] == "Tài" else "x" for s in session_details[:15]]
    pattern_str = "".join(reversed(elements))
    match = find_closest_pattern(pattern_str)

    if match:
        data = PATTERN_DATA[match]
        prediction = "Tài" if data["tai"] > data["xiu"] else "Xỉu"
        confidence = max(data["tai"], data["xiu"]) / 100
        return {
            "prediction": prediction, 
            "confidence": confidence, 
            "reason": f"[Pattern] Match: {match} ({confidence*100:.1f}%)"
        }

    return {"prediction": "Tài", "confidence": 0.5, "reason": "[Pattern] Không match pattern, fallback Tài"}

def ai_predict(session_details):
    """Dự đoán sử dụng AI qua OpenRouter API"""
    if not OPENROUTER_API_KEY:
        return {"prediction": "Tài", "confidence": 0.5, "reason": "[AI] Chưa cấu hình API key"}
    
    if not session_details:
        return {"prediction": "Tài", "confidence": 0.5, "reason": "[AI] Thiếu dữ liệu lịch sử"}

    try:
        history_data = []
        for i, session in enumerate(session_details[:15]):
            history_data.append(f"#{session['sid']}: {session['result']} (Tổng: {session['total']})")
        
        history_text = " | ".join(history_data)
        
        prompt = f"""
        PHÂN TÍCH TÀI XỈU - TRẢ LỜI: [DỰ ĐOÁN] [TỈ LỆ%] [LÝ DO]

        Lịch sử: {history_text}
        Phân tích và đưa ra dự đoán tiếp theo với tỉ lệ phần trăm.

        Định dạng: [Tài/Xỉu] [Xác suất 0-100%] [Lý do ngắn]
        """

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://lmc-gaming.ai",
            "X-Title": "LMC Gaming AI"
        }

        data = {
            "model": "google/gemma-7b-it:free",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 80,
            "temperature": 0.3,
        }

        response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result["choices"][0]["message"]["content"].strip()
            
            # Phân tích kết quả AI
            import re
            tai_match = re.search(r'Tài.*?(\d+)%', ai_response)
            xiu_match = re.search(r'Xỉu.*?(\d+)%', ai_response)
            
            if tai_match and xiu_match:
                tai_prob = int(tai_match.group(1))
                xiu_prob = int(xiu_match.group(1))
                total_prob = tai_prob + xiu_prob
                
                if total_prob > 0:
                    prediction = "Tài" if tai_prob > xiu_prob else "Xỉu"
                    confidence = max(tai_prob, xiu_prob) / 100
                    reason = f"[AI] {ai_response[:80]}..."
                else:
                    prediction, confidence, reason = "Tài", 0.5, f"[AI] Không xác định được tỉ lệ"
            else:
                ai_lower = ai_response.lower()
                if "tài" in ai_lower and "xỉu" in ai_lower:
                    tai_index = ai_response.rfind("Tài")
                    xiu_index = ai_response.rfind("Xỉu")
                    prediction = "Tài" if tai_index > xiu_index else "Xỉu"
                    confidence = 0.6
                elif "tài" in ai_lower:
                    prediction, confidence = "Tài", 0.65
                elif "xỉu" in ai_lower:
                    prediction, confidence = "Xỉu", 0.65
                else:
                    prediction, confidence = "Tài", 0.5
                
                reason = f"[AI] {ai_response[:80]}..."
            
            return {"prediction": prediction, "confidence": confidence, "reason": reason}
        else:
            return {"prediction": "Tài", "confidence": 0.5, "reason": f"[AI] Lỗi API: {response.status_code}"}

    except Exception as e:
        logging.error(f"Lỗi AI prediction: {e}")
        return {"prediction": "Tài", "confidence": 0.5, "reason": f"[AI] Lỗi: {str(e)}"}

def get_all_predictions(session_details):
    """Lấy tất cả dự đoán từ các hệ thống"""
    predictions = []
    
    # 1. Pattern prediction
    pattern_pred = pattern_predict(session_details)
    predictions.append(pattern_pred)
    
    # 2. AI prediction
    if OPENROUTER_API_KEY:
        ai_pred = ai_predict(session_details)
        predictions.append(ai_pred)
    
    # 3. LMC Gaming AI system prediction
    if session_details:
        recent_results = [s["result"][0] for s in session_details[:20]]  # 'T' hoặc 'X'
        for result in recent_results:
            lmc_system.add_result(result)
        
        lmc_pred = lmc_system.get_final_prediction()
        if lmc_pred:
            lmc_pred["prediction"] = "Tài" if lmc_pred["prediction"] == "T" else "Xỉu"
            lmc_pred["reason"] = f"[LMC AI] {lmc_pred['reason']}"
            predictions.append(lmc_pred)
    
    # 4. Trend analysis đơn giản
    if len(session_details) >= 8:
        recent = [s["result"] for s in session_details[:8]]
        tai_count = recent.count("Tài")
        xiu_count = recent.count("Xỉu")
        
        if tai_count >= 6:
            predictions.append({
                "prediction": "Xỉu",
                "confidence": 0.7,
                "reason": f"[Trend] Tài nhiều ({tai_count}/8), dự đoán Xỉu"
            })
        elif xiu_count >= 6:
            predictions.append({
                "prediction": "Tài",
                "confidence": 0.7, 
                "reason": f"[Trend] Xỉu nhiều ({xiu_count}/8), dự đoán Tài"
            })
    
    return predictions

def combined_prediction(session_details):
    """Kết hợp tất cả dự đoán và chọn cái tốt nhất"""
    all_predictions = get_all_predictions(session_details)
    
    if not all_predictions:
        return "Tài", 0.5, "Không có dự đoán nào"
    
    # Tính điểm weighted
    tai_score = 0
    xiu_score = 0
    
    for pred in all_predictions:
        weight = pred["confidence"]
        if pred["prediction"] == "Tài":
            tai_score += weight
        else:
            xiu_score += weight
    
    total_score = tai_score + xiu_score
    
    if total_score == 0:
        final_prediction, final_confidence = "Tài", 0.5
    else:
        final_prediction = "Tài" if tai_score > xiu_score else "Xỉu"
        final_confidence = max(tai_score, xiu_score) / total_score
    
    # Chọn 2 lý do có confidence cao nhất
    sorted_predictions = sorted(all_predictions, key=lambda x: x["confidence"], reverse=True)
    top_reasons = [pred["reason"] for pred in sorted_predictions[:2]]
    
    return final_prediction, final_confidence, " | ".join(top_reasons)

# ------------------------- SO SÁNH DỰ ĐOÁN PHIÊN TRƯỚC -------------------------
def check_previous_prediction(current_session_id, current_result):
    """Kiểm tra dự đoán phiên trước có đúng không"""
    previous_session_id = current_session_id - 1
    
    # Kiểm tra xem có dự đoán cho phiên trước không
    if previous_session_id in app.previous_predictions:
        previous_pred = app.previous_predictions[previous_session_id]
        was_correct = previous_pred["prediction"] == current_result
        
        # Cập nhật thống kê độ chính xác
        app.prediction_accuracy['total_predictions'] += 1
        if was_correct:
            app.prediction_accuracy['correct_predictions'] += 1
        
        # Tính tỉ lệ chính xác
        if app.prediction_accuracy['total_predictions'] > 0:
            app.prediction_accuracy['accuracy_rate'] = (
                app.prediction_accuracy['correct_predictions'] / 
                app.prediction_accuracy['total_predictions'] * 100
            )
        
        return {
            "previous_session": previous_session_id,
            "prediction": previous_pred["prediction"],
            "actual_result": current_result,
            "correct": was_correct,
            "confidence": previous_pred["confidence"],
            "reason": previous_pred["reason"]
        }
    
    return None

# ------------------------- POLL API -------------------------
def poll_api():
    while True:
        try:
            res = requests.get(API_URL, timeout=10)
            if res.status_code != 200:
                logging.warning(f"⚠️ API trả về mã {res.status_code}")
                time.sleep(POLL_INTERVAL)
                continue

            data = res.json()
            sid = data.get("sid")
            result = data.get("Ket_qua")
            total = data.get("Tong")

            if not sid or not result or total is None:
                logging.warning("⚠️ Thiếu dữ liệu từ API")
                time.sleep(POLL_INTERVAL)
                continue

            with app.lock:
                if not app.session_ids or sid > app.session_ids[-1]:
                    app.session_ids.append(sid)
                    app.history.append(result)
                    app.session_details.insert(0, {"sid": sid, "result": result, "total": total})
                    if len(app.history) > MAX_HISTORY_LEN:
                        app.history.pop(0)
                        app.session_ids.pop(0)
                        app.session_details.pop()
                    
                    # Cập nhật LMC system
                    lmc_result = "T" if result == "Tài" else "X"
                    lmc_system.add_result(lmc_result)
                    
                    # Kiểm tra dự đoán phiên trước
                    comparison = check_previous_prediction(sid, result)
                    if comparison:
                        status = "✅ ĐÚNG" if comparison["correct"] else "❌ SAI"
                        logging.info(f"🔍 So sánh phiên #{comparison['previous_session']}: Dự đoán {comparison['prediction']} - Thực tế {comparison['actual_result']} -> {status}")
                    
                    logging.info(f"✅ Phiên mới #{sid}: {result} ({total})")

        except Exception as e:
            logging.error(f"❌ Lỗi API: {e}")
        time.sleep(POLL_INTERVAL)

# ------------------------- ENDPOINT -------------------------
from datetime import datetime  

@app.route("/api/hitclub", methods=["GET"])
def get_prediction():
    try:
        with app.lock:
            if not app.history or not app.session_ids or not app.session_details:
                return jsonify({"error": "Chưa có dữ liệu"}), 500

            current_sid = app.session_ids[-1]
            current_result = app.history[-1]

            prediction, confidence, reason = combined_prediction(app.session_details)

            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            # Lưu dự đoán hiện tại cho phiên tiếp theo
            app.previous_predictions[current_sid + 1] = {
                "prediction": prediction,
                "confidence": confidence,
                "reason": reason,
                "timestamp": now_str
            }

            # Kiểm tra dự đoán phiên trước
            previous_comparison = check_previous_prediction(current_sid, current_result)

            response_data = {
                "api": "taixiu_lmc_gaming_ai",
                "current_time": now_str,
                "current_session": current_sid,
                "current_result": current_result,
                "next_session": current_sid + 1,
                "prediction": prediction,
                "confidence": round(confidence * 100, 2),
                "reason": reason,
                "system_version": "LMC Gaming AI v3.0"
            }

            # Thêm thông tin so sánh phiên trước
            if previous_comparison:
                response_data["previous_prediction_comparison"] = {
                    "session": previous_comparison["previous_session"],
                    "prediction": previous_comparison["prediction"],
                    "actual_result": previous_comparison["actual_result"],
                    "correct": previous_comparison["correct"],
                    "confidence": round(previous_comparison["confidence"] * 100, 2),
                    "status": "✅ ĐÚNG" if previous_comparison["correct"] else "❌ SAI"
                }

            # Thêm thống kê độ chính xác tổng thể
            response_data["accuracy_stats"] = {
                "total_predictions": app.prediction_accuracy['total_predictions'],
                "correct_predictions": app.prediction_accuracy['correct_predictions'],
                "accuracy_rate": round(app.prediction_accuracy['accuracy_rate'], 2)
            }

            # Thêm thông tin chi tiết từ các hệ thống con
            all_predictions = get_all_predictions(app.session_details)
            prediction_details = []
            
            for pred in all_predictions:
                prediction_details.append({
                    "system": pred["reason"].split("]")[0] + "]",
                    "prediction": pred["prediction"],
                    "confidence": round(pred["confidence"] * 100, 2)
                })
            
            response_data["prediction_details"] = prediction_details

            return jsonify(response_data)
    except Exception as e:
        logging.error(f"❌ Lỗi trong get_prediction: {e}")
        return jsonify({"error": f"Lỗi máy chủ nội bộ: {str(e)}"}), 500

@app.route("/api/history", methods=["GET"])
def get_history():
    with app.lock:
        return jsonify({
            "history": app.history,
            "session_ids": app.session_ids,
            "details": app.session_details,
            "length": len(app.history)
        })

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "history_count": len(app.history),
        "ai_configured": bool(OPENROUTER_API_KEY),
        "lmc_gaming_ai": "active",
        "total_models": 21,
        "prediction_accuracy": app.prediction_accuracy,
        "systems": ["Pattern Matching", "AI Deepseek", "LMC Gaming AI (21 models)"]
    })

@app.route("/api/lmc_status", methods=["GET"])
def lmc_status():
    return jsonify({
        "system": "LMC Gaming AI",
        "status": "active",
        "total_models": 21,
        "market_state": lmc_system.market_state,
        "session_stats": lmc_system.session_stats,
        "pattern_database_size": len(lmc_system.pattern_database),
        "prediction_accuracy": app.prediction_accuracy
    })

if __name__ == "__main__":
    threading.Thread(target=poll_api, daemon=True).start()
    port = int(os.getenv("PORT", 9099))
    logging.info(f"🚀 Khởi động LMC Gaming AI System trên port {port}")
    logging.info(f"📊 Hệ thống bao gồm 21 AI models tích hợp")
    app.run(host="0.0.0.0", port=port)
