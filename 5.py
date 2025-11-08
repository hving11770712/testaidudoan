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
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_URL = "https://hithu-ddo6.onrender.com/api/hit"
POLL_INTERVAL = 5
MAX_HISTORY_LEN = 500

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY","")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

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

# ------------------------- ULTRA DICE PREDICTION SYSTEM -------------------------
class UltraDicePredictionSystem:
    def __init__(self):
        self.history = []
        self.models = {}
        self.weights = {}
        self.performance = {}
        self.pattern_database = {}
        self.advanced_patterns = {}
        self.session_stats = {
            "streaks": {"T": 0, "X": 0, "maxT": 0, "maxX": 0},
            "transitions": {"TtoT": 0, "TtoX": 0, "XtoT": 0, "XtoX": 0},
            "volatility": 0.5,
            "pattern_confidence": {},
            "recent_accuracy": 0,
            "bias": {"T": 0, "X": 0}
        }
        self.market_state = {
            "trend": "neutral",
            "momentum": 0,
            "stability": 0.5,
            "regime": "normal"  # normal, volatile, trending, random
        }
        self.adaptive_parameters = {
            "pattern_min_length": 3,
            "pattern_max_length": 8,
            "volatility_threshold": 0.7,
            "trend_strength_threshold": 0.6,
            "pattern_confidence_decay": 0.95,
            "pattern_confidence_growth": 1.05
        }
        self.previous_top_models = []
        self.init_all_models()

    def init_all_models(self):
        for i in range(1, 22):
            model_name = f"model{i}"
            self.models[model_name] = getattr(self, model_name, lambda: None)
            self.weights[model_name] = 1
            self.performance[model_name] = {
                "correct": 0,
                "total": 0,
                "recent_correct": 0,
                "recent_total": 0,
                "streak": 0,
                "max_streak": 0
            }
        self.init_pattern_database()
        self.init_advanced_patterns()

    def init_pattern_database(self):
        self.pattern_database = {
            '1-1': {"pattern": ['T', 'X', 'T', 'X'], "probability": 0.7, "strength": 0.8},
            '1-2-1': {"pattern": ['T', 'X', 'X', 'T'], "probability": 0.65, "strength": 0.75},
            '2-1-2': {"pattern": ['T', 'T', 'X', 'T', 'T'], "probability": 0.68, "strength": 0.78},
            '3-1': {"pattern": ['T', 'T', 'T', 'X'], "probability": 0.72, "strength": 0.82},
            '1-3': {"pattern": ['T', 'X', 'X', 'X'], "probability": 0.72, "strength": 0.82},
            '2-2': {"pattern": ['T', 'T', 'X', 'X'], "probability": 0.66, "strength": 0.76},
            '2-3': {"pattern": ['T', 'T', 'X', 'X', 'X'], "probability": 0.71, "strength": 0.81},
            '3-2': {"pattern": ['T', 'T', 'T', 'X', 'X'], "probability": 0.73, "strength": 0.83},
            '4-1': {"pattern": ['T', 'T', 'T', 'T', 'X'], "probability": 0.76, "strength": 0.86},
            '1-4': {"pattern": ['T', 'X', 'X', 'X', 'X'], "probability": 0.76, "strength": 0.86},
        }

    def init_advanced_patterns(self):
        self.advanced_patterns = {
            'dynamic-1': {
                'detect': lambda data: len(data) >= 6 and 
                    data[-6:].count('T') == 4 and data[-1] == 'T',
                'predict': lambda data: 'X',
                'confidence': 0.72,
                'description': "4T trong 6 phiên, cuối là T -> dự đoán X"
            },
            'dynamic-2': {
                'detect': lambda data: len(data) >= 8 and 
                    data[-8:].count('T') >= 6 and data[-1] == 'T',
                'predict': lambda data: 'X',
                'confidence': 0.78,
                'description': "6+T trong 8 phiên, cuối là T -> dự đoán X mạnh"
            },
            'alternating-3': {
                'detect': lambda data: len(data) >= 5 and 
                    all(data[i] != data[i-1] for i in range(1, len(data[-5:]))),
                'predict': lambda data: 'X' if data[-1] == 'T' else 'T',
                'confidence': 0.68,
                'description': "5 phiên đan xen hoàn hảo -> dự đoán đảo chiều"
            }
        }

    def add_result(self, result):
        if self.history:
            last_result = self.history[-1]
            transition_key = f"{last_result}to{result}"
            self.session_stats["transitions"][transition_key] = self.session_stats["transitions"].get(transition_key, 0) + 1
            
            if result == last_result:
                self.session_stats["streaks"][result] += 1
                self.session_stats["streaks"][f"max{result}"] = max(
                    self.session_stats["streaks"][f"max{result}"],
                    self.session_stats["streaks"][result]
                )
            else:
                self.session_stats["streaks"][result] = 1
                self.session_stats["streaks"][last_result] = 0
        else:
            self.session_stats["streaks"][result] = 1
        
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
        self.session_stats["volatility"] = changes / (len(recent) - 1)

    def update_pattern_confidence(self):
        for pattern_name, confidence in list(self.session_stats["pattern_confidence"].items()):
            if len(self.history) < 2:
                continue
            
            last_result = self.history[-1]
            if pattern_name in self.advanced_patterns:
                prediction = self.advanced_patterns[pattern_name]['predict'](self.history[:-1])
                if prediction != last_result:
                    self.session_stats["pattern_confidence"][pattern_name] = max(
                        0.1, confidence * self.adaptive_parameters["pattern_confidence_decay"]
                    )
                else:
                    self.session_stats["pattern_confidence"][pattern_name] = min(
                        0.95, confidence * self.adaptive_parameters["pattern_confidence_growth"]
                    )

    def update_market_state(self):
        if len(self.history) < 15:
            return
        
        recent = self.history[-15:]
        t_count = recent.count('T')
        x_count = recent.count('X')
        
        trend_strength = abs(t_count - x_count) / len(recent)
        
        if trend_strength > self.adaptive_parameters["trend_strength_threshold"]:
            self.market_state["trend"] = 'up' if t_count > x_count else 'down'
        else:
            self.market_state["trend"] = 'neutral'
        
        momentum = 0
        for i in range(1, len(recent)):
            if recent[i] == recent[i-1]:
                momentum += 0.1 if recent[i] == 'T' else -0.1
        self.market_state["momentum"] = math.tanh(momentum)
        
        self.market_state["stability"] = 1 - self.session_stats["volatility"]
        
        if self.session_stats["volatility"] > self.adaptive_parameters["volatility_threshold"]:
            self.market_state["regime"] = 'volatile'
        elif trend_strength > 0.7:
            self.market_state["regime"] = 'trending'
        elif trend_strength < 0.3:
            self.market_state["regime"] = 'random'
        else:
            self.market_state["regime"] = 'normal'

    def update_pattern_database(self):
        if len(self.history) < 10:
            return
        
        for length in range(self.adaptive_parameters["pattern_min_length"], 
                           self.adaptive_parameters["pattern_max_length"] + 1):
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
                            "pattern": segment,
                            "probability": probability,
                            "strength": strength
                        }

    # Các model chính
    def model1(self):
        recent = self.history[-10:] if len(self.history) >= 10 else self.history
        if len(recent) < 4:
            return None
        
        patterns = self.model1_mini(recent)
        if not patterns:
            return None
        
        best_pattern = max(patterns, key=lambda x: x["probability"])
        
        confidence = best_pattern["probability"] * 0.8
        if self.market_state["regime"] == 'trending':
            confidence *= 1.1
        elif self.market_state["regime"] == 'volatile':
            confidence *= 0.9
        
        return {
            "prediction": best_pattern["prediction"],
            "confidence": min(0.95, confidence),
            "reason": f"Phát hiện pattern {best_pattern['type']} (xác suất {best_pattern['probability']:.2f})"
        }

    def model1_mini(self, data):
        patterns = []
        for pattern_type, pattern_data in self.pattern_database.items():
            pattern = pattern_data["pattern"]
            if len(data) < len(pattern):
                continue
            
            segment = data[-(len(pattern) - 1):]
            pattern_without_last = pattern[:-1]
            
            if segment == pattern_without_last:
                patterns.append({
                    "type": pattern_type,
                    "prediction": pattern[-1],
                    "probability": pattern_data["probability"],
                    "strength": pattern_data["strength"]
                })
        
        return patterns

    def model2(self):
        short_term = self.history[-5:] if len(self.history) >= 5 else self.history
        long_term = self.history[-20:] if len(self.history) >= 20 else self.history
        
        if len(short_term) < 3 or len(long_term) < 10:
            return None
        
        short_analysis = self.model2_mini(short_term)
        long_analysis = self.model2_mini(long_term)
        
        if short_analysis["trend"] == long_analysis["trend"]:
            prediction = 'T' if short_analysis["trend"] == 'up' else 'X'
            confidence = (short_analysis["strength"] + long_analysis["strength"]) / 2
            reason = f"Xu hướng ngắn và dài hạn cùng {short_analysis['trend']}"
        else:
            if short_analysis["strength"] > long_analysis["strength"] * 1.5:
                prediction = 'T' if short_analysis["trend"] == 'up' else 'X'
                confidence = short_analysis["strength"]
                reason = "Xu hướng ngắn hạn mạnh hơn dài hạn"
            else:
                prediction = 'T' if long_analysis["trend"] == 'up' else 'X'
                confidence = long_analysis["strength"]
                reason = "Xu hướng dài hạn ổn định hơn"
        
        if self.market_state["regime"] == 'trending':
            confidence *= 1.15
        elif self.market_state["regime"] == 'volatile':
            confidence *= 0.85
        
        return {
            "prediction": prediction,
            "confidence": min(0.95, confidence * 0.9),
            "reason": reason
        }

    def model2_mini(self, data):
        t_count = data.count('T')
        x_count = data.count('X')
        
        trend = 'up' if t_count > x_count else ('down' if x_count > t_count else 'neutral')
        strength = abs(t_count - x_count) / len(data)
        
        changes = sum(1 for i in range(1, len(data)) if data[i] != data[i-1])
        volatility = changes / (len(data) - 1) if len(data) > 1 else 0
        strength = strength * (1 - volatility / 2)
        
        return {"trend": trend, "strength": strength, "volatility": volatility}

    def model3(self):
        recent = self.history[-12:] if len(self.history) >= 12 else self.history
        if len(recent) < 12:
            return None
        
        analysis = self.model3_mini(recent)
        
        if analysis["difference"] < 0.4:
            return None
        
        confidence = analysis["difference"] * 0.8
        if self.market_state["regime"] == 'random':
            confidence *= 1.1
        elif self.market_state["regime"] == 'trending':
            confidence *= 0.9
        
        return {
            "prediction": analysis["prediction"],
            "confidence": min(0.95, confidence),
            "reason": f"Chênh lệch cao ({analysis['difference']*100:.0f}%) trong 12 phiên, dự đoán cân bằng"
        }

    def model3_mini(self, data):
        t_count = data.count('T')
        x_count = data.count('X')
        total = len(data)
        difference = abs(t_count - x_count) / total
        
        return {
            "difference": difference,
            "prediction": 'X' if t_count > x_count else 'T',
            "t_count": t_count,
            "x_count": x_count
        }

    # Thêm các model khác ở đây (model4 đến model21)
    # Do giới hạn độ dài, tôi chỉ thêm một số model chính

    def model4(self):
        recent = self.history[-6:] if len(self.history) >= 6 else self.history
        if len(recent) < 4:
            return None
        
        analysis = self.model4_mini(recent)
        
        if analysis["confidence"] < 0.6:
            return None
        
        confidence = analysis["confidence"]
        if self.market_state["regime"] == 'trending':
            confidence *= 1.1
        elif self.market_state["regime"] == 'volatile':
            confidence *= 0.9
        
        return {
            "prediction": analysis["prediction"],
            "confidence": min(0.95, confidence),
            "reason": f"Cầu ngắn hạn {analysis['trend']} với độ tin cậy {analysis['confidence']:.2f}"
        }

    def model4_mini(self, data):
        last_3 = data[-3:]
        t_count = last_3.count('T')
        x_count = last_3.count('X')
        
        if t_count == 3:
            return {"prediction": "T", "confidence": 0.7, "trend": "Tăng mạnh"}
        elif x_count == 3:
            return {"prediction": "X", "confidence": 0.7, "trend": "Giảm mạnh"}
        elif t_count == 2:
            return {"prediction": "T", "confidence": 0.65, "trend": "Tăng nhẹ"}
        elif x_count == 2:
            return {"prediction": "X", "confidence": 0.65, "trend": "Giảm nhẹ"}
        else:
            changes = sum(1 for i in range(1, len(data[-4:])) if data[-4:][i] != data[-4:][i-1])
            if changes >= 3:
                return {"prediction": "X" if data[-1] == 'T' else 'T', "confidence": 0.6, "trend": "Đảo chiều"}
            else:
                return {"prediction": data[-1], "confidence": 0.55, "trend": "Ổn định"}

    def model20(self):
        performance = self.model13_mini()
        best_models = [
            (model, stats) for model, stats in performance.items() 
            if stats["total"] > 10
        ]
        best_models.sort(key=lambda x: x[1]["accuracy"], reverse=True)
        best_models = best_models[:3]
        
        if not best_models:
            return None
        
        predictions = {}
        for model_name, _ in best_models:
            predictions[model_name] = self.models[model_name]()
        
        t_score = 0
        x_score = 0
        
        for model_name, prediction in predictions.items():
            if prediction and prediction["prediction"]:
                weight = performance[model_name]["accuracy"]
                if prediction["prediction"] == 'T':
                    t_score += weight * prediction["confidence"]
                else:
                    x_score += weight * prediction["confidence"]
        
        total_score = t_score + x_score
        if total_score == 0:
            return None
        
        return {
            "prediction": 'T' if t_score > x_score else 'X',
            "confidence": max(t_score, x_score) / total_score,
            "reason": f"Kết hợp {len(best_models)} model hiệu suất cao nhất"
        }

    def model13_mini(self):
        stats = {}
        for model_name, perf in self.performance.items():
            if perf["total"] > 0:
                stats[model_name] = {
                    "accuracy": perf["correct"] / perf["total"],
                    "recent_accuracy": perf["recent_correct"] / perf["recent_total"] if perf["recent_total"] > 0 else 0,
                    "total": perf["total"],
                    "recent_total": perf["recent_total"],
                    "streak": perf["streak"],
                    "max_streak": perf["max_streak"]
                }
        return stats

    def get_all_predictions(self):
        predictions = {}
        for i in range(1, 22):
            model_name = f"model{i}"
            predictions[model_name] = self.models[model_name]()
        return predictions

    def get_final_prediction(self):
        predictions = self.get_all_predictions()
        t_score = 0
        x_score = 0
        total_weight = 0
        reasons = []
        
        for model_name, prediction in predictions.items():
            if prediction and prediction["prediction"]:
                weight = self.weights.get(model_name, 1)
                score = prediction["confidence"] * weight
                
                if prediction["prediction"] == 'T':
                    t_score += score
                elif prediction["prediction"] == 'X':
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
            "prediction": final_prediction,
            "confidence": final_confidence,
            "reasons": reasons,
            "details": predictions,
            "session_stats": self.session_stats,
            "market_state": self.market_state
        }

    def adjust_confidence_by_volatility(self, confidence):
        if self.session_stats["volatility"] > 0.7:
            return confidence * 0.8
        if self.session_stats["volatility"] < 0.3:
            return min(0.95, confidence * 1.1)
        return confidence

    def update_performance(self, actual_result):
        predictions = self.get_all_predictions()
        
        for model_name, prediction in predictions.items():
            if prediction and prediction["prediction"]:
                self.performance[model_name]["total"] += 1
                self.performance[model_name]["recent_total"] += 1
                
                if prediction["prediction"] == actual_result:
                    self.performance[model_name]["correct"] += 1
                    self.performance[model_name]["recent_correct"] += 1
                    self.performance[model_name]["streak"] += 1
                    self.performance[model_name]["max_streak"] = max(
                        self.performance[model_name]["max_streak"],
                        self.performance[model_name]["streak"]
                    )
                else:
                    self.performance[model_name]["streak"] = 0
                
                if self.performance[model_name]["recent_total"] > 50:
                    self.performance[model_name]["recent_total"] -= 1
                    if (self.performance[model_name]["recent_correct"] > 0 and 
                        self.performance[model_name]["recent_correct"] / self.performance[model_name]["recent_total"] > 
                        self.performance[model_name]["correct"] / self.performance[model_name]["total"]):
                        self.performance[model_name]["recent_correct"] -= 1
                
                accuracy = self.performance[model_name]["correct"] / self.performance[model_name]["total"]
                self.weights[model_name] = max(0.1, min(2, accuracy * 2))
        
        total_predictions = sum(1 for p in predictions.values() if p and p["prediction"])
        correct_predictions = sum(1 for p in predictions.values() if p and p["prediction"] == actual_result)
        self.session_stats["recent_accuracy"] = correct_predictions / total_predictions if total_predictions > 0 else 0

# Khởi tạo hệ thống dự đoán
ultra_system = UltraDicePredictionSystem()

# ------------------------- GEMMA AI PREDICTION -------------------------
def query_gemma_ai(history_data):
    """Truy vấn model Gemma qua OpenRouter API"""
    if not OPENROUTER_API_KEY:
        logging.warning("OpenRouter API key không được cấu hình")
        return None
    
    try:
        # Chuẩn bị dữ liệu lịch sử
        history_text = ", ".join([f"Phiên {i+1}: {result}" for i, result in enumerate(history_data[-20:])])
        
        prompt = f"""
        Phân tích lịch sử kết quả tài xỉu sau và đưa ra dự đoán cho phiên tiếp theo:
        {history_text}
        
        Hãy phân tích xu hướng, pattern và đưa ra dự đoán (Tài/Xỉu) cùng độ tin cậy.
        Trả lời theo định dạng JSON: {{"prediction": "Tài hoặc Xỉu", "confidence": 0.0-1.0, "reason": "Lý do"}}
        """
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "google/gemma-3-27b-it:free",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        response = requests.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # Parse JSON response
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            prediction_data = json.loads(json_match.group())
            return prediction_data
        else:
            logging.error("Không thể parse JSON từ response Gemma AI")
            return None
            
    except Exception as e:
        logging.error(f"Lỗi khi query Gemma AI: {e}")
        return None

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
        confidence = max(data["tai"], data["xiu"]) / 100.0
        return prediction, f"[Pattern] Match: {match} ({confidence*100:.0f}%)"

    return "Tài", "[Pattern] Không match pattern, fallback Tài"

# ------------------------- COMBINED PREDICTION -------------------------
def get_combined_prediction(session_details):
    """Kết hợp dự đoán từ multiple sources"""
    try:
        # 1. Pattern-based prediction
        pattern_pred, pattern_reason = pattern_predict(session_details)
        
        # 2. Ultra System prediction
        ultra_result = None
        if ultra_system.history:
            ultra_result = ultra_system.get_final_prediction()
        
        # 3. Gemma AI prediction (nếu có API key)
        gemma_result = None
        if OPENROUTER_API_KEY and session_details:
            history_data = [s["result"] for s in session_details]
            gemma_result = query_gemma_ai(history_data)
        
        # Kết hợp các dự đoán
        predictions = []
        reasons = []
        
        # Pattern prediction
        pattern_confidence = 0.6  # Default confidence
        if "Match" in pattern_reason:
            confidence_match = re.search(r'\((\d+)%\)', pattern_reason)
            if confidence_match:
                pattern_confidence = int(confidence_match.group(1)) / 100.0
        
        predictions.append({
            "source": "Pattern",
            "prediction": pattern_pred,
            "confidence": pattern_confidence,
            "reason": pattern_reason
        })
        
        # Ultra System prediction
        if ultra_result:
            predictions.append({
                "source": "UltraSystem", 
                "prediction": "Tài" if ultra_result["prediction"] == "T" else "Xỉu",
                "confidence": ultra_result["confidence"],
                "reason": f"[Ultra] {ultra_result['reasons'][0] if ultra_result['reasons'] else 'Dự đoán tổng hợp'}"
            })
        
        # Gemma AI prediction
        if gemma_result:
            predictions.append({
                "source": "GemmaAI",
                "prediction": gemma_result["prediction"],
                "confidence": gemma_result["confidence"],
                "reason": f"[Gemma] {gemma_result['reason']}"
            })
        
        # Tính toán dự đoán cuối cùng
        if not predictions:
            return "Tài", "[Combined] Không có dự đoán nào", []
        
        # Weighted average
        tai_score = 0
        xiu_score = 0
        total_weight = 0
        
        for pred in predictions:
            weight = pred["confidence"]
            if pred["prediction"] == "Tài":
                tai_score += weight
            else:
                xiu_score += weight
            total_weight += weight
            reasons.append(f"{pred['source']}: {pred['reason']}")
        
        if total_weight == 0:
            final_prediction = "Tài"
            final_confidence = 0.5
        else:
            tai_prob = tai_score / total_weight
            xiu_prob = xiu_score / total_weight
            
            if tai_prob > xiu_prob:
                final_prediction = "Tài"
                final_confidence = tai_prob
            else:
                final_prediction = "Xỉu" 
                final_confidence = xiu_prob
        
        # Adjust confidence based on agreement
        agreement = max(tai_prob, xiu_prob)
        if agreement > 0.7:
            final_confidence = min(0.95, final_confidence * 1.1)
        elif agreement < 0.5:
            final_confidence = max(0.3, final_confidence * 0.8)
        
        combined_reason = f"[Combined] {final_prediction} (Độ tin cậy: {final_confidence*100:.1f}%)"
        
        return final_prediction, combined_reason, predictions
        
    except Exception as e:
        logging.error(f"Lỗi trong combined prediction: {e}")
        return "Tài", f"[Combined] Lỗi: {str(e)}", []

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
                    
                    # Cập nhật Ultra System
                    ultra_result = "T" if result == "Tài" else "X"
                    ultra_system.add_result(ultra_result)
                    ultra_system.update_performance(ultra_result)
                    
                    if len(app.history) > MAX_HISTORY_LEN:
                        app.history.pop(0)
                        app.session_ids.pop(0)
                        app.session_details.pop()
                    logging.info(f"✅ Phiên mới #{sid}: {result} ({total})")

        except Exception as e:
            logging.error(f"❌ Lỗi API: {e}")
        time.sleep(POLL_INTERVAL)

# ------------------------- ENDPOINT -------------------------
import re

@app.route("/api/hitclub", methods=["GET"])
def get_prediction():
    try:
        with app.lock:
            if not app.history or not app.session_ids or not app.session_details:
                return jsonify({"error": "Chưa có dữ liệu"}), 500

            current_sid = app.session_ids[-1]
            current_result = app.history[-1]

            # Sử dụng combined prediction
            prediction, reason, all_predictions = get_combined_prediction(app.session_details)

            # 👉 Thêm thời gian hiện tại
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            response_data = {
                "api": "taixiu_anhbaocx_ultra",
                "current_time": now_str,
                "current_session": current_sid,
                "current_result": current_result,
                "next_session": current_sid + 1,
                "prediction": prediction,
                "reason": reason,
                "confidence": 0.7,  # Placeholder, sẽ được tính từ combined prediction
                "all_predictions": all_predictions
            }

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
            "length": len(app.history),
            "ultra_system_stats": ultra_system.session_stats,
            "market_state": ultra_system.market_state
        })

@app.route("/api/ultra_stats", methods=["GET"])
def get_ultra_stats():
    """Endpoint để xem thống kê Ultra System"""
    performance = ultra_system.model13_mini()
    return jsonify({
        "performance": performance,
        "weights": ultra_system.weights,
        "session_stats": ultra_system.session_stats,
        "market_state": ultra_system.market_state,
        "pattern_count": len(ultra_system.pattern_database)
    })

if __name__ == "__main__":
    # Khởi tạo dữ liệu ban đầu cho Ultra System từ lịch sử hiện có
    with app.lock:
        for detail in app.session_details:
            result_char = "T" if detail["result"] == "Tài" else "X"
            ultra_system.add_result(result_char)
    
    threading.Thread(target=poll_api, daemon=True).start()
    port = int(os.getenv("PORT", 9099))
    app.run(host="0.0.0.0", port=port)
