import os
import json
import time
import logging
import threading
import requests
import math
import sys
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime

# Tăng giới hạn đệ quy để tránh lỗi
sys.setrecursionlimit(2000)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_URL = "https://hithu-ddo6.onrender.com/api/hit"
POLL_INTERVAL = 5
MAX_HISTORY_LEN = 200  # Giảm để tiết kiệm bộ nhớ

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

app = Flask(__name__)
CORS(app)
app.history = []
app.session_ids = []
app.session_details = []
app.lock = threading.Lock()

# ------------------------- SIMPLIFIED PREDICTION SYSTEM -------------------------
class SimplePredictionSystem:
    def __init__(self):
        self.history = []
        self.session_stats = {
            "t_count": 0,
            "x_count": 0,
            "current_streak": 0,
            "last_result": None,
            "volatility": 0.5
        }
        self.model_weights = {
            "trend_analysis": 1.0,
            "streak_analysis": 1.0,
            "probability_balance": 1.0,
            "momentum": 1.0
        }

    def add_result(self, result):
        """Thêm kết quả mới - an toàn và hiệu quả"""
        try:
            # Cập nhật thống kê cơ bản
            if result == "T":
                self.session_stats["t_count"] += 1
            else:
                self.session_stats["x_count"] += 1

            # Cập nhật streak
            if result == self.session_stats["last_result"]:
                self.session_stats["current_streak"] += 1
            else:
                self.session_stats["current_streak"] = 1
                self.session_stats["last_result"] = result

            self.history.append(result)
            
            # Giới hạn lịch sử
            if len(self.history) > 100:
                self.history.pop(0)
                # Điều chỉnh counts nếu cần
                if self.history[0] == "T":
                    self.session_stats["t_count"] = max(0, self.session_stats["t_count"] - 1)
                else:
                    self.session_stats["x_count"] = max(0, self.session_stats["x_count"] - 1)

            # Cập nhật volatility
            self._update_volatility()

        except Exception as e:
            logging.error(f"Lỗi trong add_result: {e}")

    def _update_volatility(self):
        """Cập nhật độ biến động"""
        try:
            if len(self.history) < 10:
                return

            recent = self.history[-10:]
            changes = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i-1])
            self.session_stats["volatility"] = changes / (len(recent) - 1)
        except Exception as e:
            logging.error(f"Lỗi trong _update_volatility: {e}")

    def trend_analysis(self):
        """Phân tích xu hướng đơn giản"""
        try:
            if len(self.history) < 5:
                return None

            recent = self.history[-5:]
            t_count = recent.count("T")
            x_count = recent.count("X")

            if t_count > x_count:
                confidence = min(0.8, t_count / 5.0 * 0.8)
                return {"prediction": "T", "confidence": confidence, "reason": f"Xu hướng Tài ({t_count}/5 phiên gần đây)"}
            else:
                confidence = min(0.8, x_count / 5.0 * 0.8)
                return {"prediction": "X", "confidence": confidence, "reason": f"Xu hướng Xỉu ({x_count}/5 phiên gần đây)"}
        except Exception as e:
            logging.error(f"Lỗi trong trend_analysis: {e}")
            return None

    def streak_analysis(self):
        """Phân tích chuỗi kết quả"""
        try:
            if len(self.history) < 2:
                return None

            current_streak = self.session_stats["current_streak"]
            current_value = self.session_stats["last_result"]

            if current_streak >= 3:
                # Dự đoán chuỗi sẽ kết thúc
                prediction = "X" if current_value == "T" else "T"
                confidence = min(0.75, current_streak * 0.2)
                return {
                    "prediction": prediction, 
                    "confidence": confidence, 
                    "reason": f"Chuỗi {current_value} kéo dài ({current_streak} phiên) - dự đoán đảo chiều"
                }
            return None
        except Exception as e:
            logging.error(f"Lỗi trong streak_analysis: {e}")
            return None

    def probability_balance(self):
        """Cân bằng xác suất"""
        try:
            if len(self.history) < 15:
                return None

            total = len(self.history)
            t_ratio = self.session_stats["t_count"] / total
            x_ratio = self.session_stats["x_count"] / total

            # Nếu một bên chiếm ưu thế, dự đoán cân bằng
            if abs(t_ratio - x_ratio) > 0.2:  # Chênh lệch >20%
                if t_ratio > x_ratio:
                    return {
                        "prediction": "X", 
                        "confidence": min(0.7, abs(t_ratio - x_ratio)), 
                        "reason": f"Cân bằng xác suất (Tài: {t_ratio:.1%}, Xỉu: {x_ratio:.1%})"
                    }
                else:
                    return {
                        "prediction": "T", 
                        "confidence": min(0.7, abs(t_ratio - x_ratio)), 
                        "reason": f"Cân bằng xác suất (Tài: {t_ratio:.1%}, Xỉu: {x_ratio:.1%})"
                    }
            return None
        except Exception as e:
            logging.error(f"Lỗi trong probability_balance: {e}")
            return None

    def momentum_analysis(self):
        """Phân tích momentum ngắn hạn"""
        try:
            if len(self.history) < 8:
                return None

            # So sánh 4 phiên gần nhất với 4 phiên trước đó
            recent = self.history[-4:]
            previous = self.history[-8:-4]

            recent_t = recent.count("T")
            previous_t = previous.count("T")

            if recent_t > previous_t:
                return {"prediction": "T", "confidence": 0.65, "reason": "Momentum Tài tăng"}
            elif recent_t < previous_t:
                return {"prediction": "X", "confidence": 0.65, "reason": "Momentum Xỉu tăng"}
            return None
        except Exception as e:
            logging.error(f"Lỗi trong momentum_analysis: {e}")
            return None

    def get_all_predictions(self):
        """Lấy tất cả dự đoán từ các model"""
        predictions = {}

        models = {
            "trend": self.trend_analysis,
            "streak": self.streak_analysis, 
            "probability": self.probability_balance,
            "momentum": self.momentum_analysis
        }

        for name, model_func in models.items():
            try:
                prediction = model_func()
                if prediction:
                    predictions[name] = prediction
            except Exception as e:
                logging.error(f"Lỗi model {name}: {e}")

        return predictions

    def get_final_prediction(self):
        """Tổng hợp dự đoán cuối cùng"""
        try:
            predictions = self.get_all_predictions()
            
            if not predictions:
                # Fallback: nếu không có dự đoán nào, dựa trên kết quả gần nhất
                if self.history:
                    last_result = self.history[-1]
                    prediction = "X" if last_result == "T" else "T"
                    return {
                        "prediction": prediction,
                        "confidence": 0.5,
                        "reason": "Không có dự đoán rõ ràng - dự đoán đảo chiều",
                        "details": {}
                    }
                else:
                    return None

            # Tính điểm tổng hợp
            t_score = 0
            x_score = 0
            details = {}

            for name, pred in predictions.items():
                weight = self.model_weights.get(name, 1.0)
                score = pred["confidence"] * weight
                
                if pred["prediction"] == "T":
                    t_score += score
                else:
                    x_score += score
                
                details[name] = {
                    "prediction": "Tài" if pred["prediction"] == "T" else "Xỉu",
                    "confidence": pred["confidence"],
                    "reason": pred["reason"]
                }

            total_score = t_score + x_score
            
            if total_score == 0:
                return None

            if t_score > x_score:
                final_prediction = "T"
                final_confidence = t_score / total_score
            else:
                final_prediction = "X" 
                final_confidence = x_score / total_score

            # Điều chỉnh confidence dựa trên volatility
            if self.session_stats["volatility"] > 0.7:
                final_confidence *= 0.8
            elif self.session_stats["volatility"] < 0.3:
                final_confidence = min(0.9, final_confidence * 1.1)

            return {
                "prediction": final_prediction,
                "confidence": final_confidence,
                "reason": f"Dự đoán tổng hợp từ {len(predictions)} model",
                "details": details,
                "session_stats": self.session_stats
            }

        except Exception as e:
            logging.error(f"Lỗi trong get_final_prediction: {e}")
            return None

# Khởi tạo hệ thống dự đoán
prediction_system = SimplePredictionSystem()

# ------------------------- AI PREDICTION -------------------------
def query_ai_prediction(history_data):
    """Truy vấn AI dự đoán - với xử lý lỗi đầy đủ"""
    if not OPENROUTER_API_KEY:
        return None

    try:
        # Giới hạn lịch sử để tránh quá dài
        recent_history = history_data[-8:]
        history_text = " -> ".join(recent_history)

        prompt = f"""
        Lịch sử kết quả tài xỉu gần đây: {history_text}
        
        Phân tích ngắn gọn và dự đoán kết quả tiếp theo là Tài hay Xỉu.
        Trả lời theo định dạng JSON: {{"prediction": "Tài hoặc Xỉu", "confidence": 0.0-1.0, "reason": "lý do ngắn"}}
        """

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com",
            "X-Title": "TaiXiu Predictor"
        }

        payload = {
            "model": "google/gemma-3-27b-it:free",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 200
        }

        response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=20)
        
        if response.status_code != 200:
            logging.warning(f"AI API trả về mã lỗi: {response.status_code}")
            return None

        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()

        # Parse JSON response
        try:
            # Tìm JSON trong response
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                json_str = content[start_idx:end_idx]
                prediction_data = json.loads(json_str)
                
                # Validate data
                if ("prediction" in prediction_data and 
                    "confidence" in prediction_data and 
                    "reason" in prediction_data):
                    return prediction_data
        except json.JSONDecodeError:
            logging.warning("Không thể parse JSON từ AI response")

        # Fallback: parse thủ công
        if "Tài" in content:
            return {"prediction": "Tài", "confidence": 0.7, "reason": "AI phân tích nghiêng Tài"}
        elif "Xỉu" in content:
            return {"prediction": "Xỉu", "confidence": 0.7, "reason": "AI phân tích nghiêng Xỉu"}

        return None

    except requests.exceptions.Timeout:
        logging.warning("AI request timeout")
        return None
    except requests.exceptions.ConnectionError:
        logging.warning("Lỗi kết nối đến AI service")
        return None
    except Exception as e:
        logging.error(f"Lỗi không xác định trong query_ai_prediction: {e}")
        return None

# ------------------------- COMBINED PREDICTION -------------------------
def get_combined_prediction(session_details):
    """Dự đoán kết hợp - an toàn và hiệu quả"""
    try:
        if not session_details:
            return "Tài", "Chưa có đủ dữ liệu lịch sử", []

        # 1. System prediction
        system_result = prediction_system.get_final_prediction()
        
        # 2. AI prediction (nếu có API key và đủ dữ liệu)
        ai_result = None
        if OPENROUTER_API_KEY and len(session_details) >= 5:
            history_data = [s["result"] for s in session_details]
            ai_result = query_ai_prediction(history_data)

        # Thu thập tất cả dự đoán
        all_predictions = []

        # System predictions
        if system_result:
            # Thêm dự đoán tổng hợp từ system
            all_predictions.append({
                "source": "System",
                "prediction": "Tài" if system_result["prediction"] == "T" else "Xỉu",
                "confidence": system_result["confidence"],
                "reason": system_result["reason"]
            })
            
            # Thêm các dự đoán chi tiết từ system
            if "details" in system_result:
                for model_name, detail in system_result["details"].items():
                    all_predictions.append({
                        "source": f"System_{model_name}",
                        "prediction": detail["prediction"],
                        "confidence": detail["confidence"],
                        "reason": detail["reason"]
                    })

        # AI prediction
        if ai_result:
            all_predictions.append({
                "source": "AI",
                "prediction": ai_result["prediction"],
                "confidence": ai_result["confidence"],
                "reason": ai_result["reason"]
            })

        # Nếu không có dự đoán nào
        if not all_predictions:
            return "Tài", "Không có dự đoán khả dụng", []

        # Tính toán dự đoán cuối cùng
        tai_score = 0
        xiu_score = 0
        total_confidence = 0

        for pred in all_predictions:
            confidence = pred["confidence"]
            total_confidence += confidence
            
            if pred["prediction"] == "Tài":
                tai_score += confidence
            else:
                xiu_score += confidence

        if total_confidence == 0:
            final_prediction = "Tài"
            final_confidence = 0.5
        else:
            if tai_score > xiu_score:
                final_prediction = "Tài"
                final_confidence = tai_score / total_confidence
            else:
                final_prediction = "Xỉu"
                final_confidence = xiu_score / total_confidence

        # Điều chỉnh confidence dựa trên sự đồng thuận
        agreement = max(tai_score, xiu_score) / total_confidence
        if agreement > 0.7:
            final_confidence = min(0.95, final_confidence * 1.1)

        reason = f"Dự đoán {final_prediction} (độ tin cậy: {final_confidence:.1%}) - tổng hợp từ {len(all_predictions)} nguồn"

        return final_prediction, reason, all_predictions

    except Exception as e:
        logging.error(f"Lỗi trong get_combined_prediction: {e}")
        return "Tài", f"Lỗi hệ thống: {str(e)}", []

# ------------------------- API POLLING -------------------------
def poll_api():
    """Lấy dữ liệu từ API - với xử lý lỗi robust"""
    consecutive_errors = 0
    max_consecutive_errors = 5

    while True:
        try:
            response = requests.get(API_URL, timeout=10)
            
            if response.status_code == 200:
                consecutive_errors = 0  # Reset error count
                data = response.json()
                
                sid = data.get("sid")
                result = data.get("Ket_qua")
                total = data.get("Tong")

                if all([sid, result, total is not None]):
                    with app.lock:
                        # Kiểm tra phiên mới
                        if not app.session_ids or sid > app.session_ids[-1]:
                            app.session_ids.append(sid)
                            app.history.append(result)
                            app.session_details.insert(0, {
                                "sid": sid, 
                                "result": result, 
                                "total": total
                            })

                            # Cập nhật prediction system
                            try:
                                result_char = "T" if result == "Tài" else "X"
                                prediction_system.add_result(result_char)
                            except Exception as e:
                                logging.error(f"Lỗi cập nhật prediction system: {e}")

                            # Giới hạn lịch sử
                            if len(app.history) > MAX_HISTORY_LEN:
                                app.history.pop(0)
                                app.session_ids.pop(0)
                                if app.session_details:
                                    app.session_details.pop()

                            logging.info(f"✅ Phiên mới #{sid}: {result} ({total})")
                else:
                    logging.warning("Dữ liệu API không đầy đủ")
            else:
                logging.warning(f"API trả về mã lỗi: {response.status_code}")
                consecutive_errors += 1

        except requests.exceptions.Timeout:
            logging.warning("⏰ Timeout khi gọi API")
            consecutive_errors += 1
        except requests.exceptions.ConnectionError:
            logging.warning("🔌 Lỗi kết nối đến API")
            consecutive_errors += 1
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Lỗi request: {e}")
            consecutive_errors += 1
        except Exception as e:
            logging.error(f"❌ Lỗi không xác định trong poll_api: {e}")
            consecutive_errors += 1

        # Nếu có quá nhiều lỗi liên tiếp, tăng thời gian chờ
        wait_time = POLL_INTERVAL
        if consecutive_errors >= max_consecutive_errors:
            wait_time = min(60, POLL_INTERVAL * 2)  # Tăng dần nhưng tối đa 60s
            logging.warning(f"Nhiều lỗi liên tiếp, tăng thời gian chờ lên {wait_time}s")

        time.sleep(wait_time)

# ------------------------- ENDPOINTS -------------------------
@app.route("/api/hitclub", methods=["GET"])
def get_prediction():
    """Endpoint dự đoán chính"""
    try:
        with app.lock:
            if not app.session_details:
                return jsonify({"error": "Chưa có dữ liệu"}), 400

            current_session = app.session_ids[-1] if app.session_ids else "N/A"
            current_result = app.history[-1] if app.history else "N/A"

            prediction, reason, all_predictions = get_combined_prediction(app.session_details)

            response_data = {
                "api": "taixiu_predictor_v2",
                "current_time": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "current_session": current_session,
                "current_result": current_result,
                "next_session": current_session + 1 if isinstance(current_session, int) else "N/A",
                "prediction": prediction,
                "reason": reason,
                "all_predictions": all_predictions,
                "total_predictions": len(all_predictions)
            }

            return jsonify(response_data)

    except Exception as e:
        logging.error(f"Lỗi endpoint /api/hitclub: {e}")
        return jsonify({"error": "Lỗi server nội bộ"}), 500

@app.route("/api/history", methods=["GET"])
def get_history():
    """Lấy lịch sử kết quả"""
    with app.lock:
        return jsonify({
            "recent_history": app.history[-20:],
            "recent_sessions": app.session_ids[-20:],
            "recent_details": app.session_details[:20],
            "total_count": len(app.history)
        })

@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Thống kê hệ thống"""
    try:
        system_stats = prediction_system.session_stats
        
        return jsonify({
            "system_stats": system_stats,
            "history_size": len(prediction_system.history),
            "app_history_size": len(app.history),
            "model_weights": prediction_system.model_weights
        })
    except Exception as e:
        logging.error(f"Lỗi endpoint /api/stats: {e}")
        return jsonify({"error": "Lỗi khi lấy thống kê"}), 500

@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "system_ready": len(prediction_system.history) > 0,
        "app_data_ready": len(app.history) > 0,
        "ai_available": bool(OPENROUTER_API_KEY)
    }
    return jsonify(health_status)

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint không tồn tại"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Lỗi server nội bộ"}), 500

# ------------------------- INITIALIZATION -------------------------
def initialize_system():
    """Khởi tạo hệ thống với dữ liệu hiện có"""
    try:
        with app.lock:
            if app.session_details:
                logging.info(f"Khởi tạo hệ thống với {len(app.session_details)} phiên lịch sử")
                
                for detail in app.session_details[:50]:  # Giới hạn số lượng
                    try:
                        result_char = "T" if detail["result"] == "Tài" else "X"
                        prediction_system.add_result(result_char)
                    except Exception as e:
                        logging.error(f"Lỗi khi thêm phiên {detail.get('sid')}: {e}")
    except Exception as e:
        logging.error(f"Lỗi khởi tạo hệ thống: {e}")

if __name__ == "__main__":
    # Khởi tạo hệ thống
    initialize_system()
    
    # Bắt đầu polling thread
    polling_thread = threading.Thread(target=poll_api, daemon=True)
    polling_thread.start()
    
    # Khởi động server
    port = int(os.getenv("PORT", 9099))
    logging.info(f"🚀 Khởi động server trên port {port}")
    
    # Sử dụng production server, không dùng debug mode
    app.run(host="0.0.0.0", port=port, debug=False)
