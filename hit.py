import os
import json
import time
import logging
import threading
import requests
from collections import Counter
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime
from UltraDicePredictionSystem import UltraDicePredictionSystem

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_URL = "https://hithu-ddo6.onrender.com/api/hit"
POLL_INTERVAL = 5
MAX_HISTORY_LEN = 500

app = Flask(__name__)
CORS(app)
app.history = []
app.session_ids = []
app.session_details = []
app.lock = threading.Lock()

# Khởi tạo hệ thống dự đoán
app.prediction_system = UltraDicePredictionSystem()

# ------------------------- PATTERN DATA (giữ nguyên) -------------------------
PATTERN_DATA = {
    # ... (giữ nguyên pattern data từ file cũ)
}

BIG_STREAK_DATA = {
    # ... (giữ nguyên big streak data từ file cũ)
}

SUM_STATS = {
    # ... (giữ nguyên sum stats từ file cũ)
}

# ------------------------- PREDICTION USING ULTRA SYSTEM -------------------------
def ultra_system_predict(session_details):
    if not session_details:
        return "Tài", "[Ultra System] Thiếu dữ liệu"

    try:
        # Chuyển đổi lịch sử sang định dạng T/X
        for session in session_details[:50]:  # Sử dụng 50 phiên gần nhất
            result_char = 'T' if session["result"] == "Tài" else 'X'
            app.prediction_system.add_result(result_char)
        
        # Lấy dự đoán từ hệ thống
        prediction_data = app.prediction_system.get_final_prediction()
        
        if prediction_data and prediction_data['prediction']:
            prediction = "Tài" if prediction_data['prediction'] == 'T' else "Xỉu"
            confidence = prediction_data['confidence'] * 100
            main_reason = prediction_data['reasons'][0] if prediction_data['reasons'] else "Dự đoán từ hệ thống AI"
            
            return prediction, f"[Ultra System] {main_reason} ({confidence:.1f}%)"
        else:
            return "Tài", "[Ultra System] Không có dự đoán, fallback Tài"
            
    except Exception as e:
        logging.error(f"Lỗi hệ thống dự đoán: {e}")
        return "Tài", f"[Ultra System] Lỗi: {str(e)}"

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
                    
                    # Cập nhật hệ thống dự đoán
                    result_char = 'T' if result == "Tài" else 'X'
                    app.prediction_system.add_result(result_char)
                    
                    if len(app.history) > MAX_HISTORY_LEN:
                        app.history.pop(0)
                        app.session_ids.pop(0)
                        app.session_details.pop()
                    logging.info(f"✅ Phiên mới #{sid}: {result} ({total})")

        except Exception as e:
            logging.error(f"❌ Lỗi API: {e}")
        time.sleep(POLL_INTERVAL)

# ------------------------- ENDPOINT -------------------------
@app.route("/api/hitclub", methods=["GET"])
def get_prediction():
    try:
        with app.lock:
            if not app.history or not app.session_ids or not app.session_details:
                return jsonify({"error": "Chưa có dữ liệu"}), 500

            current_sid = app.session_ids[-1]
            current_result = app.history[-1]

            # Sử dụng hệ thống dự đoán mới
            prediction, reason = ultra_system_predict(app.session_details)

            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            return jsonify({
                "api": "taixiu_anhbaocx_ultra",
                "current_time": now_str,
                "current_session": current_sid,
                "current_result": current_result,
                "next_session": current_sid + 1,
                "prediction": prediction,
                "reason": reason,
                "system_version": "Ultra AI Prediction System"
            })
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

@app.route("/api/system_stats", methods=["GET"])
def get_system_stats():
    try:
        with app.lock:
            prediction_data = app.prediction_system.get_final_prediction()
            return jsonify({
                "market_state": app.prediction_system.market_state,
                "session_stats": app.prediction_system.session_stats,
                "performance": app.prediction_system.performance,
                "weights": app.prediction_system.weights,
                "pattern_count": len(app.prediction_system.pattern_database)
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    threading.Thread(target=poll_api, daemon=True).start()
    port = int(os.getenv("PORT", 9099))
    app.run(host="0.0.0.0", port=port)
