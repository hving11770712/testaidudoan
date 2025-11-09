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
POLL_INTERVAL = 5
MAX_HISTORY_LEN = 500

app = Flask(__name__)
CORS(app)
app.history = []
app.session_ids = []
app.session_details = []
app.lock = threading.Lock()
app.prediction_data = {}  # Lưu trữ dữ liệu cho thuật toán dự đoán

# ------------------------- THUẬT TOÁN DỰ ĐOÁN MỚI -------------------------
def do_ben(data):
    """Đếm số lần bệt liên tiếp"""
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
            # Lấy thêm dữ liệu xúc xắc
            xuc_xac_1 = data.get("Xuc_xac_1", 0)
            xuc_xac_2 = data.get("Xuc_xac_2", 0)
            xuc_xac_3 = data.get("Xuc_xac_3", 0)

            if not sid or not result or total is None:
                logging.warning("⚠️ Thiếu dữ liệu từ API")
                time.sleep(POLL_INTERVAL)
                continue

            with app.lock:
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
                    if len(app.history) > MAX_HISTORY_LEN:
                        app.history.pop(0)
                        app.session_ids.pop(0)
                        app.session_details.pop()
                    logging.info(f"✅ Phiên mới #{sid}: {result} ({total}) - Xúc xắc: {xuc_xac_1},{xuc_xac_2},{xuc_xac_3}")

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

            current_session = app.session_details[0]
            current_sid = current_session["sid"]
            current_result = current_session["result"]
            current_total = current_session["total"]
            
            # Lấy thông tin xúc xắc
            xuc_xac_1 = current_session.get("xuc_xac_1", 0)
            xuc_xac_2 = current_session.get("xuc_xac_2", 0)
            xuc_xac_3 = current_session.get("xuc_xac_3", 0)
            xx_string = f"{xuc_xac_1}-{xuc_xac_2}-{xuc_xac_3}"
            
            # Chuẩn bị dữ liệu cho thuật toán
            data_kq = [s["result"] for s in app.session_details]
            diem_lich_su = [s["total"] for s in app.session_details]
            
            # Gọi thuật toán dự đoán
            prediction, confidence, reason = du_doan(
                data_kq, 
                dem_sai=0, 
                pattern_sai=set(), 
                xx=xx_string, 
                diem_lich_su=diem_lich_su, 
                data=app.prediction_data
            )

            # 👉 Thêm thời gian hiện tại
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            return jsonify({
                "api": "taixiu_anhbaocx",
                "current_time": now_str,  # 🕒 Thời gian thực tế
                "current_session": current_sid,
                "current_result": current_result,
                "current_total": current_total,
                "xuc_xac": f"{xuc_xac_1},{xuc_xac_2},{xuc_xac_3}",
                "next_session": current_sid + 1,
                "prediction": prediction,
                "confidence": confidence,
                "reason": reason
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

if __name__ == "__main__":
    threading.Thread(target=poll_api, daemon=True).start()
    port = int(os.getenv("PORT", 9099))
    app.run(host="0.0.0.0", port=port)
