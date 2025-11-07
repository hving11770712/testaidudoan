import os
import json
import time
import logging
import threading
import requests
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
BIG_STREAK_DATA = {
    "tai": {
        "3": {"next_tai": 65, "next_xiu": 35},
        "4": {"next_tai": 70, "next_xiu": 30},
        "5": {"next_tai": 75, "next_xiu": 25},
        "6": {"next_tai": 80, "next_xiu": 20},
        "7": {"next_tai": 85, "next_xiu": 15},
        "8": {"next_tai": 88, "next_xiu": 12},
        "9": {"next_tai": 90, "next_xiu": 10},
        "10+": {"next_tai": 92, "next_xiu": 8}
    },
    "xiu": {
        "3": {"next_tai": 35, "next_xiu": 65},
        "4": {"next_tai": 30, "next_xiu": 70},
        "5": {"next_tai": 25, "next_xiu": 75},
        "6": {"next_tai": 20, "next_xiu": 80},
        "7": {"next_tai": 15, "next_xiu": 85},
        "8": {"next_tai": 12, "next_xiu": 88},
        "9": {"next_tai": 10, "next_xiu": 90},
        "10+": {"next_tai": 8, "next_xiu": 92}
    }
}
SUM_STATS = {
    "3-10": {"tai": 0, "xiu": 100},  # Xỉu 100%
    "11": {"tai": 15, "xiu": 85},
    "12": {"tai": 25, "xiu": 75},
    "13": {"tai": 40, "xiu": 60},
    "14": {"tai": 50, "xiu": 50},
    "15": {"tai": 60, "xiu": 40},
    "16": {"tai": 75, "xiu": 25},
    "17": {"tai": 85, "xiu": 15},
    "18": {"tai": 100, "xiu": 0}     # Tài 100%
}
# ------------------------- PREDICTION USING PATTERN -------------------------
def find_closest_pattern(pattern_str):
    for key in sorted(PATTERN_DATA.keys(), key=len, reverse=True):
        if pattern_str.endswith(key):
            return key
    return None

def pattern_predict(session_details):
    if not session_details:
        return "Tài", "[Pattern] Thiếu dữ liệu"

    elements = ["t" if s["result"] == "Tài" else "x" for s in session_details[:15]]
    pattern_str = "".join(reversed(elements))
    match = find_closest_pattern(pattern_str)

    if match:
        data = PATTERN_DATA[match]
        prediction = "Tài" if data["tai"] > data["xiu"] else "Xỉu"
        confidence = max(data["tai"], data["xiu"])
        return prediction, f"[Pattern] Match: {match} ({confidence}%)"

    return "Tài", "[Pattern] Không match pattern, fallback Tài"

# ------------------------- AI PREDICTION USING DEEPSEEK V3 -------------------------
def ai_predict(session_details):
    """Dự đoán sử dụng Deepseek V3 qua OpenRouter API"""
    if not OPENROUTER_API_KEY:
        return "Tài", "[AI] Chưa cấu hình API key"
    
    if not session_details:
        return "Tài", "[AI] Thiếu dữ liệu lịch sử"

    try:
        # Chuẩn bị dữ liệu lịch sử cho AI
        history_data = []
        for i, session in enumerate(session_details[:20]):  # Lấy 20 phiên gần nhất
            history_data.append(f"Phiên {session['sid']}: {session['result']} (Tổng: {session['total']})")
        
        history_text = "\n".join(history_data)
        
        prompt = f"""
        Bạn là một chuyên gia phân tích trò chơi Tài Xỉu. Dựa vào lịch sử các phiên gần đây, hãy phân tích và dự đoán kết quả cho phiên tiếp theo.

        LỊCH SỬ GẦN ĐÂY:
        {history_text}

        PHÂN TÍCH:
        - Tổng điểm 3-10 là Xỉu, 11-17 có thể cả hai, 18 là Tài
        - Phân tích xu hướng, chuỗi liên tiếp, và sự cân bằng
        - Xác suất thống kê từ dữ liệu lịch sử

        DỰ ĐOÁN:
        Chỉ trả về một trong hai: "Tài" hoặc "Xỉu"
        Kèm theo phân tích ngắn gọn (dưới 100 từ)
        """

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 150,
            "temperature": 0.3
        }

        response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result["choices"][0]["message"]["content"].strip()
            
            # Phân tích kết quả AI
            if "Tài" in ai_response and "Xỉu" in ai_response:
                # Nếu có cả hai, xem cái nào được đề cập sau (thường là dự đoán cuối)
                tai_index = ai_response.rfind("Tài")
                xiu_index = ai_response.rfind("Xỉu")
                prediction = "Tài" if tai_index > xiu_index else "Xỉu"
            elif "Tài" in ai_response:
                prediction = "Tài"
            elif "Xỉu" in ai_response:
                prediction = "Xỉu"
            else:
                prediction = "Tài"  # Fallback
            
            return prediction, f"[AI] {ai_response[:100]}..."
        else:
            error_msg = f"Lỗi API: {response.status_code}"
            if response.text:
                error_msg += f" - {response.text[:100]}"
            return "Tài", f"[AI] {error_msg}"

    except Exception as e:
        logging.error(f"Lỗi AI prediction: {e}")
        return "Tài", f"[AI] Lỗi: {str(e)}"

# ------------------------- COMBINED PREDICTION -------------------------
def combined_prediction(session_details):
    """Kết hợp dự đoán từ pattern và AI"""
    pattern_pred, pattern_reason = pattern_predict(session_details)
    ai_pred, ai_reason = ai_predict(session_details)
    
    # Đếm số lần Tài/Xỉu gần đây
    recent_results = [s["result"] for s in session_details[:10]]
    tai_count = recent_results.count("Tài")
    xiu_count = recent_results.count("Xỉu")
    
    # Phân tích trend
    if tai_count >= 7:
        trend_pred = "Xỉu"
        trend_reason = f"[Trend] Tài nhiều ({tai_count}/10), dự đoán Xỉu"
    elif xiu_count >= 7:
        trend_pred = "Tài" 
        trend_reason = f"[Trend] Xỉu nhiều ({xiu_count}/10), dự đoán Tài"
    else:
        trend_pred = pattern_pred
        trend_reason = "[Trend] Cân bằng, dùng pattern"
    
    # Kết hợp các phương pháp
    votes = {"Tài": 0, "Xỉu": 0}
    
    # Pattern vote
    votes[pattern_pred] += 1
    
    # AI vote (chỉ tính nếu có API key)
    if OPENROUTER_API_KEY:
        votes[ai_pred] += 1
    
    # Trend vote
    votes[trend_pred] += 1
    
    # Quyết định cuối cùng
    final_prediction = max(votes, key=votes.get)
    
    reasons = []
    if pattern_reason: reasons.append(pattern_reason)
    if ai_reason: reasons.append(ai_reason)
    if trend_reason: reasons.append(trend_reason)
    
    combined_reason = " | ".join(reasons)
    
    return final_prediction, combined_reason

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
            prediction, reason = combined_prediction(app.session_details)

            # 👉 Thêm thời gian hiện tại
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            response_data = {
                "api": "taixiu_anhbaocx",
                "current_time": now_str,
                "current_session": current_sid,
                "current_result": current_result,
                "next_session": current_sid + 1,
                "prediction": prediction,
                "reason": reason
            }

            # Thêm thông tin AI nếu có API key
            if OPENROUTER_API_KEY:
                ai_pred, ai_reason = ai_predict(app.session_details)
                response_data["ai_prediction"] = ai_pred
                response_data["ai_reason"] = ai_reason

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
        "ai_configured": bool(OPENROUTER_API_KEY)
    })

if __name__ == "__main__":
    threading.Thread(target=poll_api, daemon=True).start()
    port = int(os.getenv("PORT", 9099))
    app.run(host="0.0.0.0", port=port)
