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

# ------------------------- HÙNG AKIRA AI SYSTEM -------------------------
class HungAkiraPredictionSystem:
    def __init__(self):
        self.history = []
        self.pattern_database = {}
        self.session_stats = {
            'streaks': {'T': 0, 'X': 0, 'maxT': 0, 'maxX': 0},
            'transitions': {'TtoT': 0, 'TtoX': 0, 'XtoT': 0, 'XtoX': 0},
            'volatility': 0.5,
            'recent_accuracy': 0
        }
        self.market_state = {
            'trend': 'neutral',
            'momentum': 0,
            'stability': 0.5,
            'regime': 'normal'
        }
        self.init_pattern_database()

    def init_pattern_database(self):
        self.pattern_database = {
            'T-X-T-X': {'prediction': 'X', 'confidence': 0.65, 'occurrences': 0},
            'X-T-X-T': {'prediction': 'T', 'confidence': 0.65, 'occurrences': 0},
            'T-T-X': {'prediction': 'X', 'confidence': 0.70, 'occurrences': 0},
            'X-X-T': {'prediction': 'T', 'confidence': 0.70, 'occurrences': 0},
            'T-T-T-X': {'prediction': 'X', 'confidence': 0.72, 'occurrences': 0},
            'X-X-X-T': {'prediction': 'T', 'confidence': 0.72, 'occurrences': 0},
            'T-X-X': {'prediction': 'T', 'confidence': 0.60, 'occurrences': 0},
            'X-T-T': {'prediction': 'X', 'confidence': 0.60, 'occurrences': 0}
        }

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
        if len(self.history) > 100:
            self.history.pop(0)
        
        self.update_volatility()
        self.update_market_state()
        self.update_pattern_database()

    def update_volatility(self):
        if len(self.history) < 10:
            return
        
        recent = self.history[-10:]
        changes = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i-1])
        self.session_stats['volatility'] = changes / (len(recent) - 1)

    def update_market_state(self):
        if len(self.history) < 15:
            return
        
        recent = self.history[-15:]
        t_count = recent.count('T')
        x_count = recent.count('X')
        
        trend_strength = abs(t_count - x_count) / len(recent)
        
        if trend_strength > 0.6:
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
        if self.session_stats['volatility'] > 0.7:
            self.market_state['regime'] = 'volatile'
        elif trend_strength > 0.7:
            self.market_state['regime'] = 'trending'
        elif trend_strength < 0.3:
            self.market_state['regime'] = 'random'
        else:
            self.market_state['regime'] = 'normal'

    def update_pattern_database(self):
        if len(self.history) < 8:
            return
        
        # Cập nhật tần suất pattern
        for pattern in self.pattern_database:
            pattern_list = pattern.split('-')
            count = 0
            
            for i in range(len(self.history) - len(pattern_list) + 1):
                if self.history[i:i+len(pattern_list)] == pattern_list:
                    count += 1
            
            if count > 0:
                self.pattern_database[pattern]['occurrences'] = count
                # Điều chỉnh confidence dựa trên tần suất
                base_confidence = self.pattern_database[pattern]['confidence']
                frequency_factor = min(1.0, count / 10)
                self.pattern_database[pattern]['confidence'] = min(0.9, base_confidence * (1 + frequency_factor * 0.2))

    def model_trend_analysis(self):
        """Model 2: Phân tích xu hướng"""
        if len(self.history) < 10:
            return None
        
        short_term = self.history[-5:]
        long_term = self.history[-15:]
        
        short_t = short_term.count('T')
        short_x = short_term.count('X')
        long_t = long_term.count('T')
        long_x = long_term.count('X')
        
        short_strength = abs(short_t - short_x) / len(short_term)
        long_strength = abs(long_t - long_x) / len(long_term)
        
        if short_strength > long_strength * 1.2:
            prediction = 'T' if short_t > short_x else 'X'
            confidence = short_strength * 0.8
            reason = f"Xu hướng ngắn hạn mạnh ({short_t}-{short_x})"
        else:
            prediction = 'T' if long_t > long_x else 'X'
            confidence = long_strength * 0.7
            reason = f"Xu hướng dài hạn ổn định ({long_t}-{long_x})"
        
        # Điều chỉnh theo market regime
        if self.market_state['regime'] == 'trending':
            confidence *= 1.1
        elif self.market_state['regime'] == 'volatile':
            confidence *= 0.9
        
        return {'prediction': prediction, 'confidence': confidence, 'reason': reason}

    def model_pattern_recognition(self):
        """Model 1 & 12: Nhận diện pattern"""
        if len(self.history) < 4:
            return None
        
        best_pattern = None
        best_confidence = 0
        
        # Kiểm tra các pattern ngắn
        for length in [3, 4]:
            if len(self.history) >= length:
                recent_pattern = '-'.join(self.history[-length:])
                for pattern, data in self.pattern_database.items():
                    pattern_parts = pattern.split('-')
                    if len(pattern_parts) == length + 1:
                        # So sánh pattern (không bao gồm phần tử cuối)
                        if recent_pattern == '-'.join(pattern_parts[:-1]):
                            if data['confidence'] > best_confidence:
                                best_confidence = data['confidence']
                                best_pattern = {
                                    'prediction': data['prediction'],
                                    'confidence': data['confidence'],
                                    'reason': f"Pattern {pattern} (xuất hiện {data['occurrences']} lần)"
                                }
        
        return best_pattern

    def model_mean_reversion(self):
        """Model 3: Mean reversion - cân bằng tỷ lệ"""
        if len(self.history) < 12:
            return None
        
        recent = self.history[-12:]
        t_count = recent.count('T')
        x_count = recent.count('X')
        total = len(recent)
        
        difference = abs(t_count - x_count) / total
        
        if difference > 0.4:
            prediction = 'X' if t_count > x_count else 'T'
            confidence = difference * 0.8
            return {
                'prediction': prediction,
                'confidence': confidence,
                'reason': f"Chênh lệch cao ({t_count}-{x_count}), dự đoán cân bằng"
            }
        
        return None

    def model_break_probability(self):
        """Model 10 & 16: Xác suất bẻ cầu"""
        if len(self.history) < 20:
            return {'prediction': None, 'confidence': 0.5, 'reason': "Chưa đủ dữ liệu"}
        
        # Phân tích lịch sử bẻ cầu
        break_count = 0
        total_opportunities = 0
        
        for i in range(5, len(self.history)):
            segment = self.history[i-5:i]
            if len(set(segment)) == 1:  # Chuỗi đồng nhất
                total_opportunities += 1
                if self.history[i] != segment[-1]:  # Bị bẻ
                    break_count += 1
        
        break_prob = break_count / total_opportunities if total_opportunities > 0 else 0.5
        
        # Điều chỉnh theo streak hiện tại
        current_streak = self.session_stats['streaks'][self.history[-1]] if self.history else 0
        if current_streak >= 4:
            break_prob = min(0.9, break_prob * (1 + current_streak * 0.1))
        
        return {
            'prediction': None,
            'confidence': break_prob,
            'reason': f"Xác suất bẻ cầu: {break_prob:.2f} (streak: {current_streak})"
        }

    def model_volatility_analysis(self):
        """Model 11: Phân tích biến động"""
        if len(self.history) < 10:
            return None
        
        volatility = self.session_stats['volatility']
        
        if volatility < 0.3:
            # Ít biến động, tiếp tục xu hướng
            prediction = self.history[-1]
            confidence = 0.7
            reason = f"Biến động thấp ({volatility:.2f}), tiếp tục xu hướng"
        elif volatility > 0.7:
            # Nhiều biến động, khó dự đoán
            prediction = 'T' if random.random() > 0.5 else 'X'
            confidence = 0.5
            reason = f"Biến động cao ({volatility:.2f}), dự đoán ngẫu nhiên"
        else:
            # Biến động trung bình
            trend = self.model_trend_analysis()
            if trend:
                prediction = trend['prediction']
                confidence = trend['confidence'] * 0.9
                reason = f"Biến động trung bình, theo xu hướng"
            else:
                return None
        
        return {'prediction': prediction, 'confidence': confidence, 'reason': reason}

    def get_combined_prediction(self):
        """Kết hợp tất cả các model"""
        models = [
            self.model_trend_analysis(),
            self.model_pattern_recognition(),
            self.model_mean_reversion(),
            self.model_volatility_analysis()
        ]
        
        # Lọc các model có dự đoán hợp lệ
        valid_models = [m for m in models if m and m.get('prediction')]
        
        if not valid_models:
            return None
        
        # Tính điểm tổng hợp
        t_score = 0
        x_score = 0
        reasons = []
        
        for model in valid_models:
            weight = model['confidence']
            if model['prediction'] == 'T':
                t_score += weight
            else:
                x_score += weight
            reasons.append(model['reason'])
        
        total_score = t_score + x_score
        if total_score == 0:
            return None
        
        final_prediction = 'T' if t_score > x_score else 'X'
        final_confidence = max(t_score, x_score) / total_score
        
        # Điều chỉnh confidence theo market regime
        if self.market_state['regime'] == 'volatile':
            final_confidence *= 0.9
        elif self.market_state['regime'] == 'trending':
            final_confidence *= 1.1
        
        return {
            'prediction': final_prediction,
            'confidence': final_confidence,
            'reason': ' | '.join(reasons[:2]),  # Chỉ lấy 2 lý do đầu
            'models_count': len(valid_models),
            'market_regime': self.market_state['regime']
        }

# Khởi tạo hệ thống Hùng Akira
akira_system = HungAkiraPredictionSystem()

# ------------------------- PATTERN DATA -------------------------
PATTERN_DATA = {
    # Các pattern cơ bản
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
    
    # Bổ sung pattern cầu lớn (chuỗi dài)
    "tttttttt": {"tai": 88, "xiu": 12}, "xxxxxxxx": {"tai": 12, "xiu": 88},
    "tttttttx": {"tai": 25, "xiu": 75}, "xxxxxxxxt": {"tai": 75, "xiu": 25},
    "tttttxxx": {"tai": 35, "xiu": 65}, "xxxxtttt": {"tai": 65, "xiu": 35},
    "ttttxxxx": {"tai": 30, "xiu": 70}, "xxxxtttx": {"tai": 70, "xiu": 30},
    
    # Pattern đặc biệt cho Sunwin
    "txtxtx": {"tai": 68, "xiu": 32}, "xtxtxt": {"tai": 32, "xiu": 68},
    "ttxtxt": {"tai": 55, "xiu": 45}, "xxtxtx": {"tai": 45, "xiu": 55},
    "txtxxt": {"tai": 60, "xiu": 40}, "xtxttx": {"tai": 40, "xiu": 60},
    
    # Thêm các pattern mới nâng cao
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
    
    # Pattern đặc biệt zigzag
    "txtx": {"tai": 52, "xiu": 48}, "xtxt": {"tai": 48, "xiu": 52},
    "txtxt": {"tai": 53, "xiu": 47}, "xtxtx": {"tai": 47, "xiu": 53},
    "txtxtx": {"tai": 55, "xiu": 45}, "xtxtxt": {"tai": 45, "xiu": 55},
    "txtxtxt": {"tai": 57, "xiu": 43}, "xtxtxtx": {"tai": 43, "xiu": 57},
    
    # Pattern đặc biệt kết hợp
    "ttxxttxx": {"tai": 38, "xiu": 62}, "xxttxxtt": {"tai": 62, "xiu": 38},
    "ttxxxttx": {"tai": 45, "xiu": 55}, "xxttxxxt": {"tai": 55, "xiu": 45},
    "ttxtxttx": {"tai": 50, "xiu": 50}, "xxtxtxxt": {"tai": 50, "xiu": 50},
    
    # Thêm các pattern mới cực ngon
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

# ------------------------- PREDICTION USING PATTERN -------------------------
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

# ------------------------- AI PREDICTION USING DEEPSEEK V3 -------------------------
def ai_predict(session_details):
    """Dự đoán sử dụng Deepseek V3 qua OpenRouter API"""
    if not OPENROUTER_API_KEY:
        return {"prediction": "Tài", "confidence": 0.5, "reason": "[AI] Chưa cấu hình API key"}
    
    if not session_details:
        return {"prediction": "Tài", "confidence": 0.5, "reason": "[AI] Thiếu dữ liệu lịch sử"}

    try:
        # Chuẩn bị dữ liệu lịch sử cho AI
        history_data = []
        for i, session in enumerate(session_details[:15]):
            history_data.append(f"#{session['sid']}: {session['result']} (Tổng: {session['total']})")
        
        history_text = " | ".join(history_data)
        
        prompt = f"""
        PHÂN TÍCH TÀI XỈU - TRẢ LỜI THEO ĐỊNH DẠNG: [DỰ ĐOÁN] [TỈ LỆ%] [LÝ DO]

        Lịch sử gần đây: {history_text}

        Phân tích xu hướng và đưa ra dự đoán tiếp theo.
        Tổng điểm: 3-10=Xỉu, 11-17=cân bằng, 18=Tài.
        Phân tích pattern, streak, và xác suất.

        Định dạng bắt buộc: [Tài/Xỉu] [Xác suất 0-100%] [Lý do ngắn gọn]
        """

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://taixiu.ai",
            "X-Title": "Tai Xiu AI Predictor"
        }

        # Sử dụng model free ổn định
        model = "google/gemma-7b-it:free"

        data = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 80,
            "temperature": 0.3,
            "top_p": 0.9
        }

        response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result["choices"][0]["message"]["content"].strip()
            
            # Phân tích kết quả AI với regex để lấy tỉ lệ
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
                    prediction = "Tài"
                    confidence = 0.5
                    reason = f"[AI] Không xác định được tỉ lệ: {ai_response[:50]}"
            else:
                # Fallback: phân tích đơn giản
                ai_lower = ai_response.lower()
                if "tài" in ai_lower and "xỉu" in ai_lower:
                    tai_index = ai_response.rfind("Tài")
                    xiu_index = ai_response.rfind("Xỉu")
                    prediction = "Tài" if tai_index > xiu_index else "Xỉu"
                    confidence = 0.6
                elif "tài" in ai_lower:
                    prediction = "Tài"
                    confidence = 0.65
                elif "xỉu" in ai_lower:
                    prediction = "Xỉu" 
                    confidence = 0.65
                else:
                    prediction = "Tài"
                    confidence = 0.5
                
                reason = f"[AI] {ai_response[:80]}..."
            
            return {
                "prediction": prediction,
                "confidence": confidence,
                "reason": reason
            }
        else:
            error_msg = f"Lỗi API: {response.status_code}"
            return {"prediction": "Tài", "confidence": 0.5, "reason": f"[AI] {error_msg}"}

    except Exception as e:
        logging.error(f"Lỗi AI prediction: {e}")
        return {"prediction": "Tài", "confidence": 0.5, "reason": f"[AI] Lỗi: {str(e)}"}

# ------------------------- COMBINED PREDICTION -------------------------
def get_all_predictions(session_details):
    """Lấy tất cả dự đoán từ các hệ thống"""
    predictions = []
    
    # 1. Pattern prediction
    pattern_pred = pattern_predict(session_details)
    predictions.append(pattern_pred)
    
    # 2. AI prediction (nếu có API key)
    if OPENROUTER_API_KEY:
        ai_pred = ai_predict(session_details)
        predictions.append(ai_pred)
    
    # 3. Hùng Akira system prediction
    if session_details:
        # Cập nhật dữ liệu cho Hùng Akira system
        recent_results = [s["result"][0] for s in session_details[:20]]  # 'T' hoặc 'X'
        for result in recent_results:
            akira_system.add_result(result)
        
        akira_pred = akira_system.get_combined_prediction()
        if akira_pred:
            # Chuyển đổi từ 'T','X' sang 'Tài','Xỉu'
            akira_pred["prediction"] = "Tài" if akira_pred["prediction"] == "T" else "Xỉu"
            akira_pred["reason"] = f"[Hùng Akira] {akira_pred['reason']}"
            predictions.append(akira_pred)
    
    # 4. Trend analysis (đơn giản)
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
    
    # Tính điểm cho Tài và Xỉu
    tai_score = 0
    xiu_score = 0
    reasons = []
    
    for pred in all_predictions:
        weight = pred["confidence"]
        if pred["prediction"] == "Tài":
            tai_score += weight
        else:
            xiu_score += weight
        reasons.append(pred["reason"])
    
    total_score = tai_score + xiu_score
    
    if total_score == 0:
        final_prediction = "Tài"
        final_confidence = 0.5
    else:
        final_prediction = "Tài" if tai_score > xiu_score else "Xỉu"
        final_confidence = max(tai_score, xiu_score) / total_score
    
    # Chọn 2 lý do có confidence cao nhất
    sorted_predictions = sorted(all_predictions, key=lambda x: x["confidence"], reverse=True)
    top_reasons = [pred["reason"] for pred in sorted_predictions[:2]]
    
    return final_prediction, final_confidence, " | ".join(top_reasons)

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
                    
                    # Cập nhật Hùng Akira system
                    akira_result = "T" if result == "Tài" else "X"
                    akira_system.add_result(akira_result)
                    
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

            # Sử dụng combined prediction
            prediction, confidence, reason = combined_prediction(app.session_details)

            # 👉 Thêm thời gian hiện tại
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            response_data = {
                "api": "taixiu_anhbaocx_hung_akira",
                "current_time": now_str,
                "current_session": current_sid,
                "current_result": current_result,
                "next_session": current_sid + 1,
                "prediction": prediction,
                "confidence": round(confidence * 100, 2),  # Tỉ lệ phần trăm
                "reason": reason,
                "system_version": "Hùng Akira AI v2.0"
            }

            # Thêm thông tin chi tiết từ các hệ thống con
            all_predictions = get_all_predictions(app.session_details)
            prediction_details = []
            
            for i, pred in enumerate(all_predictions):
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
        "hung_akira_system": "active",
        "systems": ["Pattern Matching", "AI Deepseek", "Hùng Akira AI"]
    })

@app.route("/api/systems", methods=["GET"])
def get_systems_info():
    return jsonify({
        "systems": {
            "pattern_matching": {
                "status": "active",
                "patterns_count": len(PATTERN_DATA),
                "description": "Hệ thống nhận diện pattern cơ bản"
            },
            "ai_deepseek": {
                "status": "active" if OPENROUTER_API_KEY else "inactive",
                "model": "Deepseek V3",
                "description": "AI thông minh qua OpenRouter"
            },
            "hung_akira_ai": {
                "status": "active",
                "models_count": 5,
                "description": "Hệ thống Hùng Akira với 5 model AI kết hợp"
            }
        }
    })

if __name__ == "__main__":
    threading.Thread(target=poll_api, daemon=True).start()
    port = int(os.getenv("PORT", 9099))
    logging.info(f"🚀 Khởi động Hùng Akira AI System trên port {port}")
    logging.info(f"📊 Hệ thống bao gồm: Pattern Matching, AI Deepseek, Hùng Akira AI")
    app.run(host="0.0.0.0", port=port)
