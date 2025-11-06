import os
import json
import time
import logging
import threading
import requests
from collections import Counter, deque
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_URL = "https://hithu-ddo6.onrender.com/api/hit"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "your-openrouter-api-key-here")
POLL_INTERVAL = 5
MAX_HISTORY_LEN = 500

app = Flask(__name__)
CORS(app)
app.history = []
app.session_ids = []
app.session_details = []
app.ai_training_data = deque(maxlen=1000)
app.lock = threading.Lock()

# ------------------------- AI PREDICTION SYSTEM -------------------------
class AIPredictionSystem:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        # Sử dụng DeepSeek V3.1 Free
        self.model = "deepseek/deepseek-chat-v3.1:free"
        self.prompt_templates = {
            'deepseek_analysis': """
Bạn là chuyên gia phân tích xác suất và pattern trong trò chơi Tài Xỉu. 

DỮ LIỆU LỊCH SỬ (mới nhất trước):
{history}

THỐNG KÊ:
- Tổng phiên: {total_sessions}
- Tỉ lệ Tài/Xỉu: {tai_ratio:.1%}/{xiu_ratio:.1%}
- Chuỗi hiện tại: {current_streak}
- Độ biến động: {volatility}
- Pattern phổ biến: {common_patterns}

PHÂN TÍCH:
Dựa trên dữ liệu lịch sử và quy luật xác suất, hãy đưa ra dự đoán kết quả tiếp theo.

CHỈ TRẢ LỜI: "Tài" hoặc "Xỉu"
            """,
            'technical_analysis': """
[PHÂN TÍCH KỸ THUẬT TÀI XỈU]

DỮ LIỆU 10 PHIÊN GẦN NHẤT:
{recent_10}

CHỈ BÁO:
- Trung bình 5 phiên: {ma5}
- Trung bình 10 phiên: {ma10} 
- Sức mạnh xu hướng: {rsi}
- Xu hướng: {trend}

PHÂN TÍCH VÀ DỰ ĐOÁN:
            """
        }
        self.performance_history = []
        self.learning_rate = 0.1

    def analyze_with_ai(self, session_details, prompt_type='deepseek_analysis'):
        """Phân tích và dự đoán sử dụng DeepSeek AI"""
        if not session_details:
            return "Tài", "[DeepSeek] Không có dữ liệu"

        try:
            # Chuẩn bị dữ liệu
            history = [s['result'] for s in session_details[:30]]
            recent_10 = [s['result'] for s in session_details[:10]]
            
            # Tính toán thống kê
            tai_count = sum(1 for s in session_details if s['result'] == 'Tài')
            xiu_count = sum(1 for s in session_details if s['result'] == 'Xỉu')
            total_sessions = len(session_details)
            tai_ratio = tai_count / total_sessions if total_sessions > 0 else 0.5
            xiu_ratio = xiu_count / total_sessions if total_sessions > 0 else 0.5
            
            current_streak = self.calculate_current_streak(session_details)
            volatility = self.calculate_volatility(session_details[:10])
            common_patterns = self.find_common_patterns(history[:15])
            
            # Tính chỉ báo kỹ thuật
            ma5 = self.calculate_moving_average(session_details[:5])
            ma10 = self.calculate_moving_average(session_details[:10])
            rsi = self.calculate_rsi(session_details[:14])

            # Chọn prompt template
            if prompt_type == 'technical_analysis':
                prompt = self.prompt_templates['technical_analysis'].format(
                    recent_10=", ".join(recent_10),
                    ma5=ma5,
                    ma10=ma10,
                    rsi=rsi,
                    trend=self.analyze_trend(session_details[:10])
                )
            else:
                prompt = self.prompt_templates['deepseek_analysis'].format(
                    history=", ".join(history),
                    total_sessions=total_sessions,
                    tai_ratio=tai_ratio,
                    xiu_ratio=xiu_ratio,
                    current_streak=current_streak,
                    volatility=volatility,
                    common_patterns=common_patterns
                )

            # Gọi API OpenRouter với DeepSeek
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://taixiu-ai-predict.com",
                "X-Title": "Tai Xiu AI Predictor"
            }

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system", 
                        "content": "Bạn là chuyên gia phân tích thống kê và xác suất. Hãy phân tích dữ liệu lịch sử Tài Xỉu và đưa ra dự đoán chính xác nhất. Chỉ trả lời bằng 'Tài' hoặc 'Xỉu'."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 20,  # Giảm tokens vì chỉ cần Tài/Xỉu
                "top_p": 0.9
            }

            response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                prediction_text = result['choices'][0]['message']['content'].strip()
                
                # Xử lý kết quả từ DeepSeek
                prediction_text_clean = prediction_text.upper().replace('"', '').replace("'", "")
                
                if "TÀI" in prediction_text_clean:
                    prediction = "Tài"
                    confidence = 0.75
                elif "XỈU" in prediction_text_clean or "XIU" in prediction_text_clean:
                    prediction = "Xỉu" 
                    confidence = 0.75
                else:
                    # Fallback analysis
                    prediction, fallback_reason = self.deepseek_fallback_analysis(session_details)
                    confidence = 0.65
                    return prediction, f"[DeepSeek Fallback] {fallback_reason}"
                
                # Lưu kết quả training
                self.record_prediction(prediction, session_details[0]['result'] if session_details else "Tài")
                
                return prediction, f"[DeepSeek V3.1] {prediction_text[:60]}... (Tin cậy: {confidence:.1%})"
            else:
                logging.error(f"DeepSeek API error: {response.status_code} - {response.text}")
                prediction, reason = self.deepseek_fallback_analysis(session_details)
                return prediction, f"[DeepSeek API Error] {reason}"

        except requests.exceptions.Timeout:
            logging.error("DeepSeek API timeout")
            prediction, reason = self.deepseek_fallback_analysis(session_details)
            return prediction, f"[DeepSeek Timeout] {reason}"
        except Exception as e:
            logging.error(f"DeepSeek analysis error: {e}")
            prediction, reason = self.deepseek_fallback_analysis(session_details)
            return prediction, f"[DeepSeek Error] {reason}"

    def calculate_current_streak(self, session_details):
        """Tính chuỗi kết quả liên tiếp hiện tại"""
        if not session_details:
            return "Không có dữ liệu"
        
        current_result = session_details[0]['result']
        streak = 1
        
        for i in range(1, min(len(session_details), 10)):  # Giới hạn 10 phiên để tránh lỗi
            if session_details[i]['result'] == current_result:
                streak += 1
            else:
                break
        
        return f"{current_result} x{streak}"

    def calculate_volatility(self, session_details):
        """Tính độ biến động"""
        if len(session_details) < 2:
            return "Thấp"
        
        try:
            changes = 0
            for i in range(1, len(session_details)):
                if session_details[i]['result'] != session_details[i-1]['result']:
                    changes += 1
            
            volatility_ratio = changes / (len(session_details) - 1)
            
            if volatility_ratio > 0.7:
                return "Rất cao"
            elif volatility_ratio > 0.5:
                return "Cao"
            elif volatility_ratio > 0.3:
                return "Trung bình"
            else:
                return "Thấp"
        except Exception:
            return "Không xác định"

    def find_common_patterns(self, history):
        """Tìm pattern phổ biến"""
        if len(history) < 3:
            return "Không đủ dữ liệu"
        
        try:
            patterns = []
            for i in range(len(history) - 2):
                pattern = "-".join(history[i:i+3])
                patterns.append(pattern)
            
            pattern_counts = Counter(patterns)
            common = pattern_counts.most_common(2)  # Giảm xuống 2 pattern
            
            return ", ".join([f"{pat}({count})" for pat, count in common])
        except Exception:
            return "Lỗi phân tích"

    def analyze_trend(self, session_details):
        """Phân tích xu hướng"""
        if len(session_details) < 3:  # Giảm yêu cầu từ 5 xuống 3
            return "Không rõ"
        
        try:
            recent_tai = sum(1 for s in session_details[:3] if s['result'] == 'Tài')
            if recent_tai >= 2:
                return "Mạnh Tài"
            elif recent_tai <= 1:
                return "Mạnh Xỉu"
            else:
                return "Cân bằng"
        except Exception:
            return "Không xác định"

    def calculate_moving_average(self, session_details):
        """Tính trung bình động"""
        if not session_details:
            return "N/A"
        
        try:
            tai_count = sum(1 for s in session_details if s['result'] == 'Tài')
            return f"{tai_count}/{len(session_details)} Tài"
        except Exception:
            return "Lỗi"

    def calculate_rsi(self, session_details):
        """Tính RSI đơn giản"""
        if len(session_details) < 2:
            return "N/A"
        
        try:
            gains = 0
            losses = 0
            changes = 0
            
            for i in range(1, len(session_details)):
                if session_details[i]['result'] != session_details[i-1]['result']:
                    changes += 1
                    if session_details[i]['result'] == 'Tài':
                        gains += 1
                    else:
                        losses += 1
            
            if changes == 0:
                return "50 (Trung tính)"
            
            rsi = (gains / changes) * 100 if changes > 0 else 50
            
            if rsi > 70:
                return f"{rsi:.0f} (Quá mua)"
            elif rsi < 30:
                return f"{rsi:.0f} (Quá bán)"
            else:
                return f"{rsi:.0f} (Trung tính)"
        except Exception:
            return "Lỗi tính toán"

    def deepseek_fallback_analysis(self, session_details):
        """Phân tích dự phòng tối ưu cho DeepSeek"""
        if not session_details:
            return "Tài", "Không có dữ liệu"
        
        try:
            # Phân tích đơn giản hơn
            recent_5 = session_details[:5]
            recent_tai = sum(1 for s in recent_5 if s['result'] == 'Tài')
            
            if recent_tai >= 4:
                return "Xỉu", "Chuỗi Tài dài, dự đoán đảo chiều"
            elif recent_tai <= 1:
                return "Tài", "Chuỗi Xỉu dài, dự đoán đảo chiều"
            else:
                # Phân tích pattern đơn giản
                last_3 = [s['result'] for s in session_details[:3]]
                if len(set(last_3)) == 1:  # Tất cả giống nhau
                    return "Xỉu" if last_3[0] == "Tài" else "Tài", "Phá vỡ chuỗi đồng nhất"
                else:
                    return "Tài", "Mặc định theo xác suất"
        except Exception as e:
            logging.error(f"Fallback analysis error: {e}")
            return "Tài", "Lỗi phân tích, mặc định Tài"

    def record_prediction(self, prediction, actual_result):
        """Ghi lại kết quả dự đoán để training"""
        try:
            self.ai_training_data.append({
                'prediction': prediction,
                'actual': actual_result,
                'timestamp': datetime.now().isoformat()
            })
            
            # Tính accuracy
            if len(self.ai_training_data) >= 10:
                recent_data = list(self.ai_training_data)[-10:]
                correct = sum(1 for data in recent_data if data['prediction'] == data['actual'])
                accuracy = correct / 10
                self.performance_history.append(accuracy)
                logging.info(f"DeepSeek Accuracy (last 10): {accuracy:.1%}")
        except Exception as e:
            logging.error(f"Error recording prediction: {e}")

    def get_performance_stats(self):
        """Lấy thống kê hiệu suất"""
        try:
            if not self.performance_history:
                return {"accuracy": 0, "total_predictions": 0}
            
            recent_performance = self.performance_history[-10:]  # Giảm từ 20 xuống 10
            avg_accuracy = sum(recent_performance) / len(recent_performance)
            
            trend = "Ổn định"
            if len(self.performance_history) > 1:
                if self.performance_history[-1] > self.performance_history[-2]:
                    trend = "Cải thiện"
                elif self.performance_history[-1] < self.performance_history[-2]:
                    trend = "Giảm sút"
            
            return {
                "accuracy": avg_accuracy,
                "total_predictions": len(self.ai_training_data),
                "recent_trend": trend
            }
        except Exception:
            return {"accuracy": 0, "total_predictions": 0, "recent_trend": "Lỗi"}

# Khởi tạo hệ thống AI
app.ai_system = AIPredictionSystem()

# ------------------------- PATTERN DATA -------------------------
PATTERN_DATA = {
    "ttt": {"tai": 70, "xiu": 30}, "xxx": {"tai": 30, "xiu": 70},
    "tt": {"tai": 65, "xiu": 35}, "xx": {"tai": 35, "xiu": 65},
    "txt": {"tai": 58, "xiu": 42}, "xtx": {"tai": 42, "xiu": 58},
    "ttx": {"tai": 60, "xiu": 40}, "xxt": {"tai": 40, "xiu": 60},
}

# ------------------------- HYBRID PREDICTION SYSTEM -------------------------
def hybrid_predict(session_details):
    """Kết hợp AI và phương pháp truyền thống"""
    if not session_details:
        return "Tài", "[Hybrid] Không có dữ liệu"

    try:
        # Sử dụng DeepSeek làm phương pháp chính
        ai_prediction, ai_reason = app.ai_system.analyze_with_ai(session_details, 'deepseek_analysis')
        
        # Kết hợp với pattern matching truyền thống
        pattern_prediction, pattern_reason = pattern_predict(session_details)
        
        # Nếu cả hai phương pháp cùng kết quả
        if ai_prediction == pattern_prediction:
            final_prediction = ai_prediction
            final_reason = f"[Hybrid] DeepSeek + Pattern đồng thuận: {ai_reason}"
        else:
            # Ưu tiên AI
            final_prediction = ai_prediction
            final_reason = f"[Hybrid] Ưu tiên DeepSeek: {ai_reason} | Pattern: {pattern_prediction}"
        
        return final_prediction, final_reason
    except Exception as e:
        logging.error(f"Hybrid prediction error: {e}")
        return pattern_predict(session_details)  # Fallback to pattern only

def pattern_predict(session_details):
    """Phương pháp pattern matching truyền thống"""
    if not session_details:
        return "Tài", "[Pattern] Thiếu dữ liệu"

    try:
        elements = ["t" if s["result"] == "Tài" else "x" for s in session_details[:10]]  # Giảm từ 15 xuống 10
        pattern_str = "".join(reversed(elements))
        
        # Tìm pattern phù hợp
        for key in sorted(PATTERN_DATA.keys(), key=len, reverse=True):
            if pattern_str.endswith(key):
                data = PATTERN_DATA[key]
                prediction = "Tài" if data["tai"] > data["xiu"] else "Xỉu"
                confidence = max(data["tai"], data["xiu"])
                return prediction, f"[Pattern] {key} ({confidence}%)"

        return "Tài", "[Pattern] Không match, fallback Tài"
    except Exception as e:
        logging.error(f"Pattern prediction error: {e}")
        return "Tài", "[Pattern] Lỗi phân tích"

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
                    
                    # Giới hạn lịch sử
                    while len(app.history) > MAX_HISTORY_LEN:
                        app.history.pop(0)
                    while len(app.session_ids) > MAX_HISTORY_LEN:
                        app.session_ids.pop(0)
                    while len(app.session_details) > MAX_HISTORY_LEN:
                        app.session_details.pop()
                    
                    logging.info(f"✅ Phiên mới #{sid}: {result} ({total})")

        except Exception as e:
            logging.error(f"❌ Lỗi API: {e}")
        time.sleep(POLL_INTERVAL)

# ------------------------- ENDPOINTS -------------------------
@app.route("/api/hitclub", methods=["GET"])
def get_prediction():
    try:
        with app.lock:
            if not app.history or not app.session_ids or not app.session_details:
                return jsonify({"error": "Chưa có dữ liệu"}), 500

            current_sid = app.session_ids[-1]
            current_result = app.history[-1]

            # Sử dụng hệ thống hybrid prediction
            prediction, reason = hybrid_predict(app.session_details)

            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            return jsonify({
                "api": "taixiu_deepseek_ai",
                "current_time": now_str,
                "current_session": current_sid,
                "current_result": current_result,
                "next_session": current_sid + 1,
                "prediction": prediction,
                "reason": reason,
                "ai_model": "DeepSeek V3.1 Free",
                "system_version": "DeepSeek AI Hybrid System"
            })
    except Exception as e:
        logging.error(f"❌ Lỗi trong get_prediction: {e}")
        return jsonify({"error": f"Lỗi máy chủ nội bộ: {str(e)}"}), 500

@app.route("/api/deepseek_predict", methods=["GET"])
def get_deepseek_prediction():
    """Endpoint riêng cho DeepSeek prediction"""
    try:
        with app.lock:
            if not app.session_details:
                return jsonify({"error": "Chưa có dữ liệu"}), 500

            prediction, reason = app.ai_system.analyze_with_ai(app.session_details, 'deepseek_analysis')
            
            return jsonify({
                "prediction": prediction,
                "reason": reason,
                "performance": app.ai_system.get_performance_stats(),
                "model": "DeepSeek V3.1 Free"
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/deepseek_technical", methods=["GET"])
def get_deepseek_technical():
    """Endpoint phân tích kỹ thuật với DeepSeek"""
    try:
        with app.lock:
            if not app.sessi
