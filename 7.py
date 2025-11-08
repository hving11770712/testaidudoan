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
MAX_HISTORY_LEN = 200

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

app = Flask(__name__)
CORS(app)
app.history = []
app.session_ids = []
app.session_details = []
app.lock = threading.Lock()

# Thêm biến để theo dõi kết quả dự đoán
app.prediction_results = {
    "total": 0,
    "correct": 0,
    "incorrect": 0,
    "accuracy": 0.0,
    "history": []
}

# ------------------------- LEGACY PREDICTION FUNCTIONS -------------------------
def do_ben(data):
    if not data:
        return 0
    last = data[-1]
    count = 0
    for i in reversed(data):
        if i == last:
            count += 1
        else:
            break
    return count if count >= 3 else 0

def du_doan(data_kq, dem_sai, pattern_sai, xx, diem_lich_su, data):
    # Đảm bảo các dict tồn tại
    if "pattern_memory" not in data:
        data["pattern_memory"] = {}
    if "error_memory" not in data:
        data["error_memory"] = {}
        
    try:
        xx_list = xx.split("-")
        tong = sum(int(x) for x in xx_list)
    except:
        xx_list = ["0","0","0"]
        tong = 0

    data_kq = data_kq[-100:] if data_kq else []
    cuoi = data_kq[-1] if data_kq else None
    pattern = "".join("T" if x == "Tài" else "X" for x in data_kq)

    # === AI tự học ===
    pattern_memory = data.get("pattern_memory", {})
    matched_pattern = None
    matched_confidence = 0
    matched_pred = None
    for pat, stats in pattern_memory.items():
        if pattern.endswith(pat):
            count = stats.get("count", 0)
            correct = stats.get("correct", 0)
            confidence = correct / count if count > 0 else 0
            if confidence > matched_confidence and count >= 3 and confidence >= 0.6:
                matched_confidence = confidence
                matched_pattern = pat
                matched_pred = stats.get("next_pred", None)
    if matched_pattern and matched_pred:
        score = 90 + int(matched_confidence * 10)
        return matched_pred, score, f"Dự đoán theo mẫu cầu đã học '{matched_pattern}' với tin cậy {matched_confidence:.2f}"

    # === AI tự học lỗi ===
    error_memory = data.get("error_memory", {})
    if len(data_kq) >= 3:
        last3 = tuple(data_kq[-3:])
        if last3 in error_memory and error_memory[last3] >= 2:
            du_doan_tx = "Xỉu" if cuoi == "Tài" else "Tài"
            return du_doan_tx, 89, f"AI tự học lỗi: mẫu {last3} đã gây sai nhiều lần → Đổi sang {du_doan_tx}"

    if dem_sai >= 4:
        du_doan_tx = "Xỉu" if cuoi == "Tài" else "Tài"
        return du_doan_tx, 87, f"AI phát hiện sai liên tiếp {dem_sai} → Đổi sang {du_doan_tx}"

    if len(data_kq) >= 5:
        if data_kq[-5:].count("Tài") == data_kq[-5:].count("Xỉu") and data_kq[-1] != data_kq[-2]:
            du_doan_tx = "Xỉu" if cuoi == "Tài" else "Tài"
            return du_doan_tx, 88, "AI phát hiện dấu hiệu đổi cầu → Đổi hướng"

    # --- Phần cũ giữ nguyên ---
    if len(data_kq) < 1:
        if tong >= 16:
            return "Tài", 98, f"Tay đầu đặc biệt → Tổng {tong} >=16 → Tài"
        if tong <= 6:
            return "Xỉu", 98, f"Tay đầu đặc biệt → Tổng {tong} <=6 → Xỉu"
        return ("Tài" if tong >= 11 else "Xỉu"), 75, f"Tay đầu → Dựa tổng: {tong}"

    if len(data_kq) == 1:
        if tong >= 16:
            return "Tài", 98, f"Tay 2 → Tổng {tong} >=16 → Tài"
        if tong <= 6:
            return "Xỉu", 98, f"Tay 2 → Tổng {tong} <=6 → Xỉu"
        du_doan_tx = "Xỉu" if cuoi == "Tài" else "Tài"
        return du_doan_tx, 80, f"Tay đầu dự đoán ngược kết quả trước ({cuoi})"

    ben = do_ben(data_kq)
    counts = {"Tài": data_kq.count("Tài"), "Xỉu": data_kq.count("Xỉu")}
    chenh = abs(counts["Tài"] - counts["Xỉu"])
    diem_lich_su.append(tong)
    if len(diem_lich_su) > 6:
        diem_lich_su.pop(0)

    if len(pattern) >= 9:
        for i in range(4, 7):
            if len(pattern) >= i*2:
                sub1 = pattern[-i*2:-i]
                sub2 = pattern[-i:]
                if sub1 == "T"*i and sub2 == "X"*i:
                    return "Xỉu", 90, f"Phát hiện cầu bệt-bệt: {sub1 + sub2}"
                if sub1 == "X"*i and sub2 == "T"*i:
                    return "Tài", 90, f"Phát hiện cầu bệt-bệt: {sub1 + sub2}"

    if len(diem_lich_su) >= 3 and len(set(diem_lich_su[-3:])) == 1:
        return ("Tài" if tong % 2 == 1 else "Xỉu"), 96, f"3 lần lặp điểm: {tong}"
    if len(diem_lich_su) >= 2 and diem_lich_su[-1] == diem_lich_su[-2]:
        return ("Tài" if tong % 2 == 0 else "Xỉu"), 94, f"Kép điểm: {tong}"

    if len(set(xx_list)) == 1:
        so = xx_list[0]
        if so in ["1", "2", "4"]:
            return "Xỉu", 97, f"3 xúc xắc {so} → Xỉu"
        if so in ["3", "5"]:
            return "Tài", 97, f"3 xúc xắc {so} → Tài"
        if so == "6" and ben >= 3:
            return "Tài", 97, f"3 xúc xắc 6 + bệt → Tài"

    if ben >= 3:
        if cuoi == "Tài":
            if ben >= 5 and "3" not in xx_list:
                if not data.get("da_be_tai"):
                    data["da_be_tai"] = True
                    return "Xỉu", 80, "⚠️ Bệt Tài ≥5 chưa có xx3 → Bẻ thử"
                else:
                    return "Tài", 90, "Ôm tiếp bệt Tài chờ xx3"
            elif "3" in xx_list:
                data["da_be_tai"] = False
                return "Xỉu", 95, "Bệt Tài + Xí ngầu 3 → Bẻ"
        elif cuoi == "Xỉu":
            if ben >= 5 and "5" not in xx_list:
                if not data.get("da_be_xiu"):
                    data["da_be_xiu"] = True
                    return "Tài", 80, "⚠️ Bệt Xỉu ≥5 chưa có xx5 → Bẻ thử"
                else:
                    return "Xỉu", 90, "Ôm tiếp bệt Xỉu chờ xx5"
            elif "5" in xx_list:
                data["da_be_xiu"] = False
                return "Tài", 95, "Bệt Xỉu + Xí ngầu 5 → Bẻ"
        return cuoi, 93, f"Bệt {cuoi} ({ben} tay)"

    def ends(pats):
        return any(pattern.endswith(p) for p in pats)

    cau_mau = {
        "1-1": ["TXTX", "XTXT", "TXTXT", "XTXTX"],
        "2-2": ["TTXXTT", "XXTTXX", "TTXXTTX", "XXTTXXT"],
        "3-3": ["TTTXXX", "XXXTTT"],
        "1-2-3": ["TXXTTT", "XTTXXX"],
        "3-2-1": ["TTTXXT", "XXXTTX"],
        "1-2-1": ["TXXT", "XTTX"],
        "2-1-1-2": ["TTXTXX", "XXTXTT"],
        "2-1-2": ["TTXTT", "XXTXX"],
        "3-1-3": ["TTTXTTT", "XXXTXXX"],
        "1-2": ["TXX", "XTT"],
        "2-1": ["TTX", "XXT"],
        "1-3-2": ["TXXXTT", "XTTTXX"],
        "1-2-4": ["TXXTTTT", "XTTXXXX"],
        "1-5-3": ["TXXXXXTTT", "XTTTTXXX"],
        "5-1-3": ["TTTTXTTT", "XXXXXTXXX"],
        "1-4-2": ["TXXXXTT", "XTTTTXX"],
        "1-3-5": ["TXXXTTTTT", "XTTTXXXXX"]
    }

    for loai, mau_list in cau_mau.items():
        for mau in mau_list:
            if pattern.endswith(mau):
                return ("Xỉu" if cuoi == "Tài" else "Tài"), 90, f"Phát hiện cầu {loai}"

    if len(data_kq) >= 6:
        last_6 = data_kq[-6:]
        for i in range(2, 6):
            if i * 2 <= len(last_6):
                seq = last_6[-i*2:]
                alt1 = []
                alt2 = []
                for j in range(i*2):
                    alt1.append("Tài" if j % 2 == 0 else "Xỉu")
                    alt2.append("Xỉu" if j % 2 == 0 else "Tài")
                if seq == alt1 or seq == alt2:
                    return ("Tài" if cuoi == "Xỉu" else "Xỉu"), 90, f"Bẻ cầu 1-1 ({i*2} tay)"

    if dem_sai >= 3:
        return ("Xỉu" if cuoi == "Tài" else "Tài"), 88, "Sai 3 lần → Đổi chiều"
    if tuple(data_kq[-3:]) in pattern_sai:
        return ("Xỉu" if cuoi == "Tài" else "Tài"), 86, "Mẫu sai cũ"
    if chenh >= 3:
        uu = "Tài" if counts["Tài"] > counts["Xỉu"] else "Xỉu"
        return uu, 84, f"Lệch {chenh} cầu → Ưu tiên {uu}"

    return cuoi, 72, "Không rõ mẫu → Theo tay gần nhất"

# ------------------------- COMBINED PREDICTION SYSTEM -------------------------
class CombinedPredictionSystem:
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
            "momentum": 1.0,
            "legacy_system": 1.2  # Trọng số cao hơn cho hệ thống legacy
        }
        
        # Legacy system variables
        self.legacy_data = {
            "dem_sai": 0,
            "pattern_sai": set(),
            "diem_lich_su": [],
            "data": {
                "pattern_memory": {},
                "error_memory": {},
                "da_be_tai": False,
                "da_be_xiu": False
            }
        }

    def add_result(self, result, xx_str="0-0-0"):
        """Thêm kết quả mới - kết hợp cả hai hệ thống"""
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
                removed = self.history.pop(0)
                if removed == "T":
                    self.session_stats["t_count"] = max(0, self.session_stats["t_count"] - 1)
                else:
                    self.session_stats["x_count"] = max(0, self.session_stats["x_count"] - 1)

            # Cập nhật legacy system
            self._update_legacy_system(result, xx_str)
            
            # Cập nhật volatility
            self._update_volatility()

        except Exception as e:
            logging.error(f"Lỗi trong add_result: {e}")

    def _update_legacy_system(self, result, xx_str):
        """Cập nhật hệ thống legacy"""
        try:
            # Chuyển đổi kết quả sang định dạng legacy
            data_kq = ["Tài" if r == "T" else "Xỉu" for r in self.history]
            
            # Cập nh điểm lịch sử
            try:
                xx_list = xx_str.split("-")
                tong = sum(int(x) for x in xx_list)
                self.legacy_data["diem_lich_su"].append(tong)
                if len(self.legacy_data["diem_lich_su"]) > 6:
                    self.legacy_data["diem_lich_su"].pop(0)
            except:
                pass
            
            # Cập nhật đếm sai (đơn giản hóa)
            if len(data_kq) >= 2:
                last_prediction = self.legacy_data.get("last_prediction")
                if last_prediction and last_prediction != result:
                    self.legacy_data["dem_sai"] += 1
                    # Lưu pattern sai
                    if len(data_kq) >= 4:
                        pattern_sai_key = tuple(data_kq[-4:-1])
                        self.legacy_data["pattern_sai"].add(pattern_sai_key)
                else:
                    self.legacy_data["dem_sai"] = max(0, self.legacy_data["dem_sai"] - 1)
                    
        except Exception as e:
            logging.error(f"Lỗi cập nhật legacy system: {e}")

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

    def legacy_prediction(self, xx_str="0-0-0"):
        """Dự đoán từ hệ thống legacy"""
        try:
            if len(self.history) < 1:
                return None
                
            # Chuyển đổi dữ liệu sang định dạng legacy
            data_kq = ["Tài" if r == "T" else "Xỉu" for r in self.history]
            
            # Gọi hàm dự đoán legacy
            prediction, score, reason = du_doan(
                data_kq, 
                self.legacy_data["dem_sai"],
                self.legacy_data["pattern_sai"],
                xx_str,
                self.legacy_data["diem_lich_su"],
                self.legacy_data["data"]
            )
            
            # Lưu dự đoán cuối cùng để theo dõi sai số
            self.legacy_data["last_prediction"] = "T" if prediction == "Tài" else "X"
            
            return {
                "prediction": "T" if prediction == "Tài" else "X",
                "confidence": score / 100.0,
                "reason": f"[Legacy] {reason}"
            }
            
        except Exception as e:
            logging.error(f"Lỗi trong legacy_prediction: {e}")
            return None

    def get_all_predictions(self, xx_str="0-0-0"):
        """Lấy tất cả dự đoán từ các model"""
        predictions = {}

        models = {
            "trend": self.trend_analysis,
            "streak": self.streak_analysis, 
            "probability": self.probability_balance,
            "momentum": self.momentum_analysis,
            "legacy": lambda: self.legacy_prediction(xx_str)
        }

        for name, model_func in models.items():
            try:
                prediction = model_func()
                if prediction:
                    predictions[name] = prediction
            except Exception as e:
                logging.error(f"Lỗi model {name}: {e}")

        return predictions

    def get_final_prediction(self, xx_str="0-0-0"):
        """Tổng hợp dự đoán cuối cùng"""
        try:
            predictions = self.get_all_predictions(xx_str)
            
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
prediction_system = CombinedPredictionSystem()

# ------------------------- AI PREDICTION -------------------------
def query_ai_prediction(history_data):
    """Truy vấn AI dự đoán - với xử lý lỗi đầy đủ"""
    if not OPENROUTER_API_KEY:
        logging.info("OpenRouter API key không có, bỏ qua AI prediction")
        return None

    try:
        # Giới hạn lịch sử để tránh quá dài
        recent_history = history_data[-8:]
        history_text = " -> ".join(recent_history)

        prompt = f"""
        Lịch sử kết quả tài xỉu gần đây: {history_text}
        
        Phân tích ngắn gọn và dự đoán kết quả tiếp theo là Tài hay Xỉu.
        Trả lời theo định dạng JSON: {{"prediction": "Tài hoặc Xỉu", "confidence": 0.0-1.0, "reason": "lý do ngắn"}}
        Chỉ trả lời bằng JSON, không thêm text nào khác.
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

        logging.info(f"Gửi request đến AI với {len(recent_history)} phiên lịch sử")
        response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logging.warning(f"AI API trả về mã lỗi: {response.status_code}")
            return None

        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()
        logging.info(f"AI response: {content}")

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
                    
                    # Validate prediction value
                    if prediction_data["prediction"] not in ["Tài", "Xỉu"]:
                        logging.warning(f"AI trả về prediction không hợp lệ: {prediction_data['prediction']}")
                        return None
                    
                    # Validate confidence range
                    confidence = float(prediction_data["confidence"])
                    if not (0 <= confidence <= 1):
                        logging.warning(f"AI trả về confidence không hợp lệ: {confidence}")
                        return None
                    
                    logging.info(f"AI prediction thành công: {prediction_data['prediction']} với confidence {confidence}")
                    return prediction_data
        except json.JSONDecodeError as e:
            logging.warning(f"Không thể parse JSON từ AI response: {e}")

        # Fallback: parse thủ công nếu JSON không hợp lệ
        if "Tài" in content:
            return {"prediction": "Tài", "confidence": 0.7, "reason": "AI phân tích nghiêng Tài"}
        elif "Xỉu" in content:
            return {"prediction": "Xỉu", "confidence": 0.7, "reason": "AI phân tích nghiêng Xỉu"}

        logging.warning("Không thể parse AI response")
        return None

    except requests.exceptions.Timeout:
        logging.warning("AI request timeout sau 30 giây")
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

        # Lấy thông tin xúc xắc của phiên hiện tại để dùng cho legacy system
        current_xx = "0-0-0"
        if session_details and "xuc_xac_1" in session_details[0]:
            current_xx = f"{session_details[0]['xuc_xac_1']}-{session_details[0]['xuc_xac_2']}-{session_details[0]['xuc_xac_3']}"

        # 1. Combined System prediction
        system_result = prediction_system.get_final_prediction(current_xx)
        
        # 2. AI prediction (nếu có API key và đủ dữ liệu)
        ai_result = None
        if OPENROUTER_API_KEY and len(session_details) >= 5:
            try:
                history_data = [s["result"] for s in session_details]
                ai_result = query_ai_prediction(history_data)
            except Exception as e:
                logging.error(f"Lỗi khi gọi AI: {e}")
                ai_result = None

        # Thu thập tất cả dự đoán
        all_predictions = []

        # System predictions
        if system_result:
            # Thêm dự đoán tổng hợp từ system
            all_predictions.append({
                "source": "CombinedSystem",
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

# ------------------------- PREDICTION TRACKING -------------------------
def update_prediction_result(session_id, predicted, actual):
    """Cập nhật kết quả dự đoán"""
    try:
        with app.lock:
            app.prediction_results["total"] += 1
            
            if predicted == actual:
                app.prediction_results["correct"] += 1
                status = "ĐÚNG"
                logging.info(f"✅ Dự đoán ĐÚNG cho phiên #{session_id}: Dự đoán {predicted}, Thực tế {actual}")
            else:
                app.prediction_results["incorrect"] += 1
                status = "SAI"
                logging.info(f"❌ Dự đoán SAI cho phiên #{session_id}: Dự đoán {predicted}, Thực tế {actual}")
            
            # Tính độ chính xác
            if app.prediction_results["total"] > 0:
                app.prediction_results["accuracy"] = (
                    app.prediction_results["correct"] / app.prediction_results["total"]
                )
            
            # Lưu lịch sử
            app.prediction_results["history"].append({
                "session_id": session_id,
                "predicted": predicted,
                "actual": actual,
                "status": status,
                "timestamp": datetime.now().isoformat()
            })
            
            # Giới hạn lịch sử
            if len(app.prediction_results["history"]) > 100:
                app.prediction_results["history"].pop(0)
                
    except Exception as e:
        logging.error(f"Lỗi khi cập nhật kết quả dự đoán: {e}")

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
                xuc_xac_1 = data.get("Xuc_xac_1")
                xuc_xac_2 = data.get("Xuc_xac_2") 
                xuc_xac_3 = data.get("Xuc_xac_3")

                if all([sid, result, total is not None]):
                    with app.lock:
                        # Kiểm tra phiên mới
                        if not app.session_ids or sid > app.session_ids[-1]:
                            # Kiểm tra dự đoán cho phiên trước
                            if app.session_ids:
                                last_sid = app.session_ids[-1]
                                # Tìm dự đoán cho phiên trước
                                for detail in app.session_details:
                                    if detail.get("prediction") and detail.get("sid") == last_sid:
                                        predicted = detail["prediction"]
                                        update_prediction_result(last_sid, predicted, result)
                                        break
                            
                            app.session_ids.append(sid)
                            app.history.append(result)
                            
                            xx_str = f"{xuc_xac_1}-{xuc_xac_2}-{xuc_xac_3}"
                            session_data = {
                                "sid": sid, 
                                "result": result, 
                                "total": total,
                                "xuc_xac_1": xuc_xac_1,
                                "xuc_xac_2": xuc_xac_2,
                                "xuc_xac_3": xuc_xac_3
                            }
                            
                            app.session_details.insert(0, session_data)

                            # Cập nhật prediction system
                            try:
                                result_char = "T" if result == "Tài" else "X"
                                prediction_system.add_result(result_char, xx_str)
                            except Exception as e:
                                logging.error(f"Lỗi cập nhật prediction system: {e}")

                            # Giới hạn lịch sử
                            if len(app.history) > MAX_HISTORY_LEN:
                                app.history.pop(0)
                                app.session_ids.pop(0)
                                if app.session_details:
                                    app.session_details.pop()

                            # Log với thông tin xúc xắc
                            logging.info(f"✅ Phiên mới #{sid}: {result} ({total}) - Xúc xắc: {xuc_xac_1}, {xuc_xac_2}, {xuc_xac_3}")
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
            wait_time = min(60, POLL_INTERVAL * 2)
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
            
            # Lấy thông tin xúc xắc của phiên hiện tại
            current_details = app.session_details[0] if app.session_details else {}
            xuc_xac_1 = current_details.get("xuc_xac_1", "N/A")
            xuc_xac_2 = current_details.get("xuc_xac_2", "N/A")
            xuc_xac_3 = current_details.get("xuc_xac_3", "N/A")

            prediction, reason, all_predictions = get_combined_prediction(app.session_details)
            
            # Lưu dự đoán vào session details
            if app.session_details:
                app.session_details[0]["prediction"] = prediction

            # Thống kê kết quả gần nhất
            latest_stats = {
                "total_predictions": app.prediction_results["total"],
                "correct_predictions": app.prediction_results["correct"],
                "accuracy": round(app.prediction_results["accuracy"] * 100, 2),
                "recent_results": app.prediction_results["history"][-5:]  # 5 kết quả gần nhất
            }

            response_data = {
                "api": "taixiu_predictor_combined",
                "current_time": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "current_session": current_session,
                "current_result": current_result,
                "xuc_xac_1": xuc_xac_1,
                "xuc_xac_2": xuc_xac_2,
                "xuc_xac_3": xuc_xac_3,
                "next_session": current_session + 1 if isinstance(current_session, int) else "N/A",
                "prediction": prediction,
                "reason": reason,
                "all_predictions": all_predictions,
                "total_predictions": len(all_predictions),
                "prediction_stats": latest_stats
            }

            return jsonify(response_data)

    except Exception as e:
        logging.error(f"Lỗi endpoint /api/hitclub: {e}")
        return jsonify({"error": "Lỗi server nội bộ"}), 500

@app.route("/api/history", methods=["GET"])
def get_history():
    """Lấy lịch sử kết quả"""
    with app.lock:
        # Thêm thông tin xúc xắc vào response history
        detailed_history = []
        for detail in app.session_details[:20]:
            detailed_history.append({
                "sid": detail.get("sid"),
                "result": detail.get("result"),
                "total": detail.get("total"),
                "xuc_xac_1": detail.get("xuc_xac_1", "N/A"),
                "xuc_xac_2": detail.get("xuc_xac_2", "N/A"),
                "xuc_xac_3": detail.get("xuc_xac_3", "N/A"),
                "prediction": detail.get("prediction", "N/A")
            })
            
        return jsonify({
            "recent_history": detailed_history,
            "total_count": len(app.history)
        })

@app.route("/api/prediction_stats", methods=["GET"])
def get_prediction_stats():
    """Thống kê kết quả dự đoán"""
    with app.lock:
        return jsonify({
            "total_predictions": app.prediction_results["total"],
            "correct_predictions": app.prediction_results["correct"],
            "incorrect_predictions": app.prediction_results["incorrect"],
            "accuracy": round(app.prediction_results["accuracy"] * 100, 2),
            "history": app.prediction_results["history"][-50:]  # 50 kết quả gần nhất
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
            "model_weights": prediction_system.model_weights,
            "legacy_stats": {
                "dem_sai": prediction_system.legacy_data["dem_sai"],
                "pattern_sai_count": len(prediction_system.legacy_data["pattern_sai"]),
                "diem_lich_su": prediction_system.legacy_data["diem_lich_su"]
            }
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
        "ai_available": bool(OPENROUTER_API_KEY),
        "prediction_tracking": app.prediction_results["total"] > 0
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
                
                for detail in app.session_details[:50]:
                    try:
                        result_char = "T" if detail["result"] == "Tài" else "X"
                        xx_str = f"{detail.get('xuc_xac_1', '0')}-{detail.get('xuc_xac_2', '0')}-{detail.get('xuc_xac_3', '0')}"
                        prediction_system.add_result(result_char, xx_str)
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
    
    app.run(host="0.0.0.0", port=port, debug=False)
