"""
Flask Web Server for Edge-AI Posture Dashboard
Complete pipeline: Camera → Pose → Landmarks → Calibration → Angles → Classification → Scoring → Feedback
"""

from flask import Flask, jsonify, Response
from flask_cors import CORS
import cv2
import math as m
import mediapipe as mp
from collections import deque
import threading
from datetime import datetime
import time

app = Flask(__name__)
CORS(app)

# =====================================================
# Configuration
# =====================================================

class Config:
    DEBUG = True
    HOST = '0.0.0.0'
    PORT = 5000
    CAMERA_ENABLED = True
    FPS = 30

# =====================================================
# Posture Analyzer
# =====================================================

def findDistance(x1, y1, x2, y2):
    return m.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

def findAngle(x1, y1, x2, y2):
    try:
        theta = m.acos((y2 - y1) * (-y1) /
                       (m.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) * y1))
        return int(180 / m.pi) * theta
    except:
        return 0

class PostureAnalyzer:
    def __init__(self, fps=30):
        self.fps = fps
        self.good_frames = 0
        self.bad_frames = 0
        self.total_frames = 0

        self.calibrating = True
        self.calibration_frames = int(5 * fps)  # 5 seconds
        self.calibration_count = 0
        self.neck_base = []
        self.torso_base = []

        self.score_buffer = deque(maxlen=10)
        self.good_duration = 0
        self.bad_duration = 0
        self.frame_count = 0

    def is_calibrating(self):
        return self.calibrating

    def calibrate(self, neck_angle, torso_angle):
        """Accumulate baseline angles during calibration period"""
        if self.calibrating:
            self.calibration_count += 1
            self.neck_base.append(neck_angle)
            self.torso_base.append(torso_angle)
            
            # Check if calibration is complete
            if self.calibration_count >= self.calibration_frames:
                self.base_neck = sum(self.neck_base) / len(self.neck_base)
                self.base_torso = sum(self.torso_base) / len(self.torso_base)
                self.calibrating = False
                print(f"✓ Calibration complete! Base neck: {self.base_neck:.1f}°, Base torso: {self.base_torso:.1f}°")

    def analyze(self, neck_angle, torso_angle):
        """Analyze posture based on calibration baseline"""
        self.frame_count += 1
        
        if self.calibrating:
            # Still calibrating, just accumulate data
            self.calibrate(neck_angle, torso_angle)
            return "CALIBRATING", 0, "Calibrating posture... Sit straight", neck_angle, torso_angle
        
        # Post-calibration analysis
        self.total_frames += 1
        
        # Calculate deviations from baseline
        neck_diff = abs(neck_angle - self.base_neck)
        torso_diff = abs(torso_angle - self.base_torso)
        
        # Determine posture status based on thresholds
        if neck_angle < 40 and torso_angle < 10:
            self.good_frames += 1
            self.bad_frames = 0
            raw_score = 15  # Good posture = low risk
            status = "GOOD"
            message = "✓ Excellent posture! Keep it up 👏"
        elif neck_diff < 15 and torso_diff < 10:
            self.good_frames += 1
            self.bad_frames = 0
            raw_score = 25
            status = "GOOD"
            message = "✓ Good posture. Keep it up!"
        elif neck_diff < 25 or torso_diff < 15:
            self.bad_frames += 1
            self.good_frames = 0
            raw_score = 55
            status = "POOR"
            message = "⚠ Straighten your back slightly"
        else:
            self.bad_frames += 1
            self.good_frames = 0
            raw_score = min(100, int(neck_diff * 2 + torso_diff * 1.5))
            status = "RISKY"
            message = "🚨 Prolonged slouch detected - adjust your posture"
        
        # Smooth the score over 10 frames
        self.score_buffer.append(raw_score)
        smooth_score = int(sum(self.score_buffer) / len(self.score_buffer))
        
        # Track durations
        if status == "GOOD":
            self.good_duration += 1
        else:
            self.bad_duration += 1
        
        return status, smooth_score, message, neck_angle, torso_angle

# =====================================================
# Global State
# =====================================================

analyzer = PostureAnalyzer(Config.FPS)
current_frame = None
current_data = {
    'status': 'INITIALIZING',
    'score': 0,
    'message': 'Initializing camera...',
    'neck_angle': 0,
    'torso_angle': 0,
    'calibrated': False,
    'calibrating': True,
    'good_duration': 0,
    'bad_duration': 0,
    'fps': 0
}
camera_lock = threading.Lock()
data_lock = threading.Lock()

# FPS tracking
frame_times = deque(maxlen=30)

# =====================================================
# Routes
# =====================================================

@app.route('/')
def index():
    """Serve the main dashboard"""
    with open('index.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/style.css')
def serve_css():
    """Serve CSS file"""
    with open('style.css', 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'text/css'}

@app.route('/app.js')
def serve_js():
    """Serve JavaScript file"""
    with open('app.js', 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'text/javascript'}

@app.route('/api/status')
def get_status():
    """Get current analysis status with all metrics"""
    global frame_times
    
    with data_lock:
        data = current_data.copy()
    
    # Calculate real FPS
    if len(frame_times) > 1:
        time_diffs = []
        times = list(frame_times)
        for i in range(1, len(times)):
            time_diffs.append(times[i] - times[i-1])
        if time_diffs:
            avg_time_diff = sum(time_diffs) / len(time_diffs)
            if avg_time_diff > 0:
                data['fps'] = int(1.0 / avg_time_diff)
    
    data['timestamp'] = datetime.now().isoformat()
    return jsonify(data)

@app.route('/api/video_feed')
def video_feed():
    """Stream video frames with skeleton overlay"""
    def generate():
        while True:
            with camera_lock:
                if current_frame is not None:
                    frame = current_frame.copy()
                else:
                    time.sleep(0.1)
                    continue
            
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            time.sleep(0.033)  # ~30 FPS
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'camera_enabled': Config.CAMERA_ENABLED
    })

# =====================================================
# Camera Thread
# =====================================================

def camera_thread_worker():
    """Background thread for camera processing with pose detection"""
    global current_frame, analyzer, current_data, frame_times
    
    if not Config.CAMERA_ENABLED:
        return

    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Failed to open camera")
            return
            
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, Config.FPS)

        mp_pose = mp.solutions.pose
        pose = mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        mp_drawing = mp.solutions.drawing_utils

        print("✓ Camera initialized, starting pose detection...")
        frame_count = 0

        while True:
            try:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue
                
                # Track frame time for FPS calculation
                current_time = time.time()
                frame_times.append(current_time)
                frame_count += 1

                # Flip for selfie view and process
                frame = cv2.flip(frame, 1)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(frame_rgb)

                h, w, c = frame.shape

                if results.pose_landmarks:
                    # Draw full skeleton
                    try:
                        mp_drawing.draw_landmarks(
                            frame,
                            results.pose_landmarks,
                            mp_pose.POSE_CONNECTIONS,
                            landmark_drawing_spec=mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                            connection_drawing_spec=mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2)
                        )
                    except:
                        pass  # Skip skeleton drawing on error

                    # Extract key landmarks for posture analysis
                    try:
                        # Get landmarks list
                        lm = results.pose_landmarks.landmark
                        
                        # Head, shoulders, hips for angle calculation
                        lShoulder = [lm[11].x * w, lm[11].y * h]
                        rShoulder = [lm[12].x * w, lm[12].y * h]
                        lHip = [lm[23].x * w, lm[23].y * h]
                        rHip = [lm[24].x * w, lm[24].y * h]
                        lEar = [lm[3].x * w, lm[3].y * h]
                        rEar = [lm[4].x * w, lm[4].y * h]

                        # Calculate neck angle (head to shoulder)
                        mid_shoulder = [(lShoulder[0] + rShoulder[0]) / 2, (lShoulder[1] + rShoulder[1]) / 2]
                        mid_ear = [(lEar[0] + rEar[0]) / 2, (lEar[1] + rEar[1]) / 2]
                        neck_angle = findAngle(mid_shoulder[0], mid_shoulder[1], mid_ear[0], mid_ear[1])

                        # Calculate torso angle (shoulder to hip)
                        mid_hip = [(lHip[0] + rHip[0]) / 2, (lHip[1] + rHip[1]) / 2]
                        torso_angle = findAngle(mid_shoulder[0], mid_shoulder[1], mid_hip[0], mid_hip[1])

                        # Analyze posture
                        status, score, message, neck_angle, torso_angle = analyzer.analyze(neck_angle, torso_angle)

                        # Add message text overlay with background
                        text_color = (0, 255, 0) if status == "GOOD" else (0, 165, 255) if status == "POOR" else (0, 0, 255)
                        if status == "CALIBRATING":
                            text_color = (0, 165, 255)
                        
                        cv2.putText(frame, message, (20, 50), cv2.FONT_HERSHEY_SIMPLEX,
                                   1.2, text_color, 2)

                        # Add calibration progress if still calibrating
                        if analyzer.is_calibrating():
                            cal_progress = int(analyzer.calibration_count / analyzer.calibration_frames * 100)
                            cal_text = f'CALIBRATING... {cal_progress}%'
                            cv2.rectangle(frame, (20, 100), (400, 150), (255, 165, 0), -1)
                            cv2.putText(frame, cal_text, (30, 130),
                                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
                        
                        # Update global state
                        with data_lock:
                            current_data['status'] = status
                            current_data['score'] = score
                            current_data['message'] = message
                            current_data['neck_angle'] = round(neck_angle, 1)
                            current_data['torso_angle'] = round(torso_angle, 1)
                            current_data['calibrated'] = not analyzer.is_calibrating()
                            current_data['calibrating'] = analyzer.is_calibrating()
                            current_data['good_duration'] = analyzer.good_duration // Config.FPS
                            current_data['bad_duration'] = analyzer.bad_duration // Config.FPS

                    except Exception as e:
                        pass  # Skip analysis on error, continue processing frames

                # Update frame
                with camera_lock:
                    current_frame = frame

                time.sleep(1 / Config.FPS)
                
            except Exception as e:
                print(f"Frame processing error: {e}")
                time.sleep(0.1)
                continue

    except Exception as e:
        print(f"❌ Camera thread error: {e}")
    finally:
        try:
            cap.release()
        except:
            pass

# =====================================================
# Main
# =====================================================

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 Edge-AI Posture Dashboard Server (LIVE CAMERA)")
    print("=" * 60)
    print(f"🌐 Server running at: http://localhost:{Config.PORT}")
    print("📹 Camera: ENABLED (Real-time video streaming)")
    print("🧠 Pipeline: Camera → Pose → Angles → Scoring → Feedback")
    print("=" * 60 + "\n")

    # Start camera thread
    camera_thread = threading.Thread(target=camera_thread_worker, daemon=True)
    camera_thread.start()
    print("✓ Camera thread started\n")

    # Start Flask server
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, use_reloader=False, threaded=True)
