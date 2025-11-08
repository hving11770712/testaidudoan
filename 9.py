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

API_URL = "https://apihithu.onrender.com/api/hit"
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
app.last_prediction_result = None  # Lưu kết quả dự đoán cuối cùng để so sánh

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
            "momentum": 1.0,
            "pattern_ai": 1.2  # Trọng số cao hơn cho AI pattern
        }
        
        # Dữ liệu cho AI pattern
        self.pattern_ai_data = {
            "pattern_memory": {},
            "error_memory": {},
            "da_be_tai": False,
            "da_be_xiu": False
        }
        self.diem_lich_su = []  # Lịch sử điểm
        self.dem_sai = 0  # Đếm số lần sai liên tiếp
        self.pattern_sai = set()  # Các pattern sai

    def add_result(self, result, xx_data=None):
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
            
            # Cập nhật lịch sử điểm nếu có dữ liệu xúc xắc
            if xx_data and len(xx_data) == 3:
                try:
                    tong = sum(int(x) for x in xx_data)
                    self.diem_lich_su.append(tong)
                    if len(self.diem_lich_su) > 6:
                        self.diem_lich_su.pop(0)
                except:
                    pass
            
            # Cập nhật đếm sai và pattern sai
            if hasattr(app, 'last_prediction_result') and app.last_prediction_result:
                last_pred = app.last_prediction_result.get('prediction', '')
                actual = "Tài" if result == "T" else "Xỉu"
                
                if last_pred != actual:
                    self.dem_sai += 1
                    # Lưu pattern sai (3 kết quả gần nhất)
                    if len(self.history) >= 3:
                        pattern_sai_key = tuple(self.history[-3:])
                        self.pattern_sai.add(pattern_sai_key)
                else:
                    self.dem_sai = 0
            
            # Giới hạn lịch sử
            if len(self.history) > 100:
                removed_result = self.history.pop(0)
                # Điều chỉnh counts nếu cần
                if removed_result == "T":
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

    def pattern_ai_analysis(self, xx_data=None):
        """AI Pattern Analysis - Tích hợp hệ thống dự đoán AI pattern"""
        try:
            if not self.history or len(self.history) < 1:
                return None

            # Chuẩn bị dữ liệu đầu vào
            data_kq = ["Tài" if x == "T" else "Xỉu" for x in self.history]
            
            # Tạo chuỗi xx từ dữ liệu xúc xắc
            xx = "0-0-0"
            if xx_data and len(xx_data) == 3:
                xx = f"{xx_data[0]}-{xx_data[1]}-{xx_data[2]}"

            # Gọi hàm dự đoán AI pattern
            prediction, score, reason = self.du_doan(
                data_kq, 
                self.dem_sai, 
                self.pattern_sai, 
                xx, 
                self.diem_lich_su, 
                self.pattern_ai_data
            )

            # Chuyển đổi kết quả về định dạng chuẩn
            pred_char = "T" if prediction == "Tài" else "X"
            confidence = score / 100.0  # Chuyển điểm thành confidence (0-1)

            return {
                "prediction": pred_char,
                "confidence": confidence,
                "reason": reason
            }

        except Exception as e:
            logging.error(f"Lỗi trong pattern_ai_analysis: {e}")
            return None

    def du_doan(self, data_kq, dem_sai, pattern_sai, xx, diem_lich_su, data):
        """Hệ thống dự đoán AI pattern - với xử lý lỗi"""
        try:
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

            ben = self.do_ben(data_kq)
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

        except Exception as e:
            logging.error(f"Lỗi trong du_doan: {e}")
            return "Tài", 50, f"Dự phòng do lỗi: {str(e)}"

    def do_ben(self, data_kq):
        """Tính độ bệt (số lần lặp lại liên tiếp của kết quả cuối)"""
        if not data_kq:
            return 0
            
        count = 1
        last = data_kq[-1]
        
        for i in range(len(data_kq)-2, -1, -1):
            if data_kq[i] == last:
                count += 1
            else:
                break
                
        return count

    def get_all_predictions(self, xx_data=None):
        """Lấy tất cả dự đoán từ các model - với fallback nếu model lỗi"""
        predictions = {}

        models = {
            "trend": self.trend_analysis,
            "streak": self.streak_analysis, 
            "probability": self.probability_balance,
            "momentum": self.momentum_analysis,
            "pattern_ai": lambda: self.pattern_ai_analysis(xx_data)
        }

        for name, model_func in models.items():
            try:
                prediction = model_func()
                if prediction:
                    predictions[name] = prediction
                else:
                    logging.warning(f"Model {name} trả về None")
            except Exception as e:
                logging.error(f"Lỗi model {name}: {e}")
                # Fallback: chuyển sang model khác nếu có lỗi
                if name == "pattern_ai":
                    # Thử fallback model đơn giản nếu pattern_ai lỗi
                    try:
                        fallback_pred = self.trend_analysis()
                        if fallback_pred:
                            predictions["trend_fallback"] = fallback_pred
                            logging.info("Đã sử dụng trend analysis fallback cho pattern_ai")
                    except Exception as fallback_e:
                        logging.error(f"Fallback cũng bị lỗi: {fallback_e}")

        return predictions

    def get_final_prediction(self, xx_data=None):
        """Tổng hợp dự đoán cuối cùng"""
        try:
            predictions = self.get_all_predictions(xx_data)
            
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
    """Truy vấn AI dự đoán - với xử lý lỗi đầy đủ và fallback model"""
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

        # Thử model chính đầu tiên
        models_to_try = [
            "google/gemma-3-27b-it:free",
            "meta-llama/llama-3.1-8b-instruct:free",  # Fallback model
            "microsoft/wizardlm-2-8x22b:free"  # Fallback thứ 2
        ]

        for model in models_to_try:
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 200
                }

                response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=20)
                
                if response.status_code == 200:
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
                                logging.info(f"✅ AI prediction thành công với model {model}")
                                return prediction_data
                    except json.JSONDecodeError:
                        logging.warning(f"Không thể parse JSON từ AI response với model {model}")
                        continue

                else:
                    logging.warning(f"AI API trả về mã lỗi {response.status_code} với model {model}")
                    continue

            except requests.exceptions.Timeout:
                logging.warning(f"AI request timeout với model {model}")
                continue
            except requests.exceptions.ConnectionError:
                logging.warning(f"Lỗi kết nối đến AI service với model {model}")
                continue
            except Exception as e:
                logging.error(f"Lỗi không xác định với model {model}: {e}")
                continue

        # Fallback: parse thủ công nếu tất cả model đều lỗi
        logging.info("Tất cả AI model đều lỗi, sử dụng fallback parsing")
        for model in models_to_try:
            try:
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 200
                }

                response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=20)
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"].strip()

                    if "Tài" in content:
                        return {"prediction": "Tài", "confidence": 0.7, "reason": "AI phân tích nghiêng Tài (fallback)"}
                    elif "Xỉu" in content:
                        return {"prediction": "Xỉu", "confidence": 0.7, "reason": "AI phân tích nghiêng Xỉu (fallback)"}
            except:
                continue

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

        # Lấy dữ liệu xúc xắc từ phiên gần nhất
        xx_data = None
        if session_details and "xuc_xac_1" in session_details[0]:
            xx_data = [
                session_details[0].get("xuc_xac_1", 0),
                session_details[0].get("xuc_xac_2", 0), 
                session_details[0].get("xuc_xac_3", 0)
            ]

        # 1. System prediction
        system_result = prediction_system.get_final_prediction(xx_data)
        
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
                xuc_xac_1 = data.get("Xuc_xac_1", 0)
                xuc_xac_2 = data.get("Xuc_xac_2", 0)
                xuc_xac_3 = data.get("Xuc_xac_3", 0)

                if all([sid, result, total is not None]):
                    with app.lock:
                        # Kiểm tra phiên mới
                        if not app.session_ids or sid > app.session_ids[-1]:
                            app.session_ids.append(sid)
                            app.history.append(result)
                            app.session_details.insert(0, {
                                "sid": sid, 
                                "result": result, 
                                "total": total,
                                "xuc_xac_1": xuc_xac_1,
                                "xuc_xac_2": xuc_xac_2,
                                "xuc_xac_3": xuc_xac_3
                            })

                            # Cập nhật prediction system
                            try:
                                result_char = "T" if result == "Tài" else "X"
                                xx_data = [xuc_xac_1, xuc_xac_2, xuc_xac_3]
                                prediction_system.add_result(result_char, xx_data)
                                
                                # So sánh với dự đoán trước đó
                                if app.last_prediction_result:
                                    last_pred = app.last_prediction_result.get('prediction', '')
                                    if last_pred:
                                        status = "✅ ĐÚNG" if last_pred == result else "❌ SAI"
                                        logging.info(f"SO SÁNH DỰ ĐOÁN: Phiên {sid} - Dự đoán: {last_pred} - Thực tế: {result} -> {status}")
                                        
                                        # Cập nhật pattern memory nếu dự đoán đúng
                                        if last_pred == result and len(prediction_system.history) >= 2:
                                            # Lấy pattern trước đó
                                            pattern_key = "".join(prediction_system.history[-2:])
                                            if pattern_key not in prediction_system.pattern_ai_data["pattern_memory"]:
                                                prediction_system.pattern_ai_data["pattern_memory"][pattern_key] = {
                                                    "count": 0,
                                                    "correct": 0,
                                                    "next_pred": result
                                                }
                                            prediction_system.pattern_ai_data["pattern_memory"][pattern_key]["count"] += 1
                                            prediction_system.pattern_ai_data["pattern_memory"][pattern_key]["correct"] += 1
                                
                                # Reset last prediction
                                app.last_prediction_result = None
                                
                            except Exception as e:
                                logging.error(f"Lỗi cập nhật prediction system: {e}")

                            # Giới hạn lịch sử
                            if len(app.history) > MAX_HISTORY_LEN:
                                app.history.pop(0)
                                app.session_ids.pop(0)
                                if app.session_details:
                                    app.session_details.pop()

                            logging.info(f"✅ Phiên mới #{sid}: {result} ({total}) - Xúc xắc: [{xuc_xac_1}, {xuc_xac_2}, {xuc_xac_3}]")
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
            
            # Lấy thông tin xúc xắc từ phiên gần nhất
            xuc_xac_info = {}
            if app.session_details and "xuc_xac_1" in app.session_details[0]:
                xuc_xac_info = {
                    "xuc_xac_1": app.session_details[0].get("xuc_xac_1", 0),
                    "xuc_xac_2": app.session_details[0].get("xuc_xac_2", 0),
                    "xuc_xac_3": app.session_details[0].get("xuc_xac_3", 0)
                }

            prediction, reason, all_predictions = get_combined_prediction(app.session_details)
            
            # Lưu kết quả dự đoán để so sánh sau
            app.last_prediction_result = {
                "session": current_session + 1 if isinstance(current_session, int) else "N/A",
                "prediction": prediction,
                "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            }

            response_data = {
                "api": "taixiu_predictor_v3",
                "current_time": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "current_session": current_session,
                "current_result": current_result,
                "next_session": current_session + 1 if isinstance(current_session, int) else "N/A",
                "prediction": prediction,
                "reason": reason,
                "all_predictions": all_predictions,
                "total_predictions": len(all_predictions),
                "xuc_xac": xuc_xac_info
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
            "pattern_ai_stats": {
                "pattern_memory_size": len(prediction_system.pattern_ai_data.get("pattern_memory", {})),
                "error_memory_size": len(prediction_system.pattern_ai_data.get("error_memory", {})),
                "dem_sai": prediction_system.dem_sai,
                "pattern_sai_size": len(prediction_system.pattern_sai),
                "diem_lich_su": prediction_system.diem_lich_su
            },
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
        "ai_available": bool(OPENROUTER_API_KEY),
        "pattern_ai_ready": len(prediction_system.pattern_ai_data.get("pattern_memory", {})) > 0
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
                        xx_data = [
                            detail.get("xuc_xac_1", 0),
                            detail.get("xuc_xac_2", 0),
                            detail.get("xuc_xac_3", 0)
                        ]
                        prediction_system.add_result(result_char, xx_data)
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
