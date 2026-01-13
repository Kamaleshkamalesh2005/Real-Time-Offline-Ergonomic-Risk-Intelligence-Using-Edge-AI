import cv2
import time
import math as m
import mediapipe as mp
from collections import deque
import sys
from datetime import datetime, timedelta

import PyQt5
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QRect, QPropertyAnimation, QEasingCurve, QSize
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QBrush, QPen, QLinearGradient
from PyQt5.QtCore import QPoint
import numpy as np

# =====================================================
# Utility Functions
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

# =====================================================
# Posture Analyzer Class
# =====================================================

class PostureAnalyzer:
    def __init__(self, fps):
        self.fps = fps
        self.good_frames = 0
        self.bad_frames = 0
        self.total_frames = 0

        self.calibrated = False
        self.calibration_frames = int(4 * fps)
        self.neck_base = []
        self.torso_base = []

        self.score_buffer = deque(maxlen=10)
        
        self.good_duration = 0
        self.bad_duration = 0
        self.last_status = None

    def calibrate(self, neck_angle, torso_angle):
        self.neck_base.append(neck_angle)
        self.torso_base.append(torso_angle)

        if len(self.neck_base) >= self.calibration_frames:
            self.base_neck = sum(self.neck_base) / len(self.neck_base)
            self.base_torso = sum(self.torso_base) / len(self.torso_base)
            self.calibrated = True

    def analyze(self, neck_angle, torso_angle):
        self.total_frames += 1
        neck_diff = abs(neck_angle - self.base_neck)
        torso_diff = abs(torso_angle - self.base_torso)

        if neck_angle < 40 and torso_angle < 10:
            self.good_frames += 1
            self.bad_frames = 0
            raw_score = 10
            status = "GOOD"
            message = "Great posture! Keep it up 👏"
        else:
            self.bad_frames += 1
            self.good_frames = 0
            raw_score = min(100, int(neck_diff * 2 + torso_diff * 3))
            status = "POOR" if raw_score < 60 else "RISKY"
            message = "Straighten your back slightly" if status == "POOR" else "⚠ Prolonged slouch detected"

        self.score_buffer.append(raw_score)
        smooth_score = int(sum(self.score_buffer) / len(self.score_buffer))
        
        # Update duration tracking
        if status == "GOOD":
            self.good_duration += 1
        else:
            self.bad_duration += 1

        return status, smooth_score, message, neck_angle, torso_angle

# =====================================================
# Video Capture Thread
# =====================================================

class VideoCaptureThread(QThread):
    frame_ready = pyqtSignal(np.ndarray, dict)
    
    def __init__(self, analyzer):
        super().__init__()
        self.analyzer = analyzer
        self.running = True
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose()
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS)) or 30

    def run(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break

            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self.pose.process(rgb)

            data = {
                'frame': frame,
                'landmarks': None,
                'neck_angle': 0,
                'torso_angle': 0,
                'status': 'INITIALIZING',
                'score': 0,
                'message': 'Initializing...',
                'calibrated': self.analyzer.calibrated
            }

            if result.pose_landmarks:
                lm = result.pose_landmarks.landmark
                PL = self.mp_pose.PoseLandmark

                l_shldr = (int(lm[PL.LEFT_SHOULDER].x * w), int(lm[PL.LEFT_SHOULDER].y * h))
                r_shldr = (int(lm[PL.RIGHT_SHOULDER].x * w), int(lm[PL.RIGHT_SHOULDER].y * h))
                l_ear = (int(lm[PL.LEFT_EAR].x * w), int(lm[PL.LEFT_EAR].y * h))
                l_hip = (int(lm[PL.LEFT_HIP].x * w), int(lm[PL.LEFT_HIP].y * h))

                neck_angle = findAngle(l_shldr[0], l_shldr[1], l_ear[0], l_ear[1])
                torso_angle = findAngle(l_hip[0], l_hip[1], l_shldr[0], l_shldr[1])

                if not self.analyzer.calibrated:
                    self.analyzer.calibrate(neck_angle, torso_angle)
                    data['message'] = 'Calibrating... Sit straight'
                else:
                    status, score, msg, neck, torso = self.analyzer.analyze(neck_angle, torso_angle)
                    data['status'] = status
                    data['score'] = score
                    data['message'] = msg

                data['landmarks'] = {
                    'l_shldr': l_shldr,
                    'r_shldr': r_shldr,
                    'l_ear': l_ear,
                    'l_hip': l_hip,
                    'lm': lm
                }
                data['neck_angle'] = neck_angle
                data['torso_angle'] = torso_angle

            self.frame_ready.emit(frame, data)
            time.sleep(1 / self.fps)

    def stop(self):
        self.running = False
        self.cap.release()

# =====================================================
# Custom Widgets
# =====================================================

class RoundedFrame(QFrame):
    def __init__(self, radius=12):
        super().__init__()
        self.radius = radius
        self.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(30, 41, 59, 0.8);
                border-radius: {radius}px;
                border: 1px solid rgba(148, 163, 184, 0.2);
            }}
        """)

class MetricCard(RoundedFrame):
    def __init__(self, title, value, unit=""):
        super().__init__(radius=12)
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel(title)
        title_font = QFont("Poppins", 11)
        title_font.setWeight(QFont.Normal)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: rgba(226, 232, 240, 0.7);")
        
        # Value
        value_label = QLabel(value)
        value_font = QFont("Courier New", 28)
        value_font.setWeight(QFont.Bold)
        value_label.setFont(value_font)
        value_label.setStyleSheet("color: #38BDF8;")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addStretch()
        self.setLayout(layout)
        self.value_label = value_label

class CircularProgressWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.value = 0
        self.setMinimumSize(QSize(180, 180))
        self.setMaximumSize(QSize(180, 180))
        self.setStyleSheet("background-color: transparent; border: none;")
        
    def setValue(self, val):
        self.value = min(100, max(0, val))
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center = QPoint(90, 90)
        radius = 70
        
        # Background circle
        painter.setPen(QPen(QColor(71, 85, 105), 8))
        painter.drawEllipse(center, radius, radius)
        
        # Progress arc
        color = QColor("#22C55E")
        if self.value > 60:
            color = QColor("#FACC15")
        if self.value > 80:
            color = QColor("#EF4444")
        
        painter.setPen(QPen(color, 8))
        painter.drawArc(QRect(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
                       90 * 16, -int(360 * self.value / 100) * 16)
        
        # Center text
        painter.setFont(QFont("Courier New", 32, QFont.Bold))
        painter.setPen(QPen(color))
        painter.drawText(QRect(center.x() - radius, center.y() - 20, radius * 2, 80),
                        Qt.AlignCenter, f"{self.value}")
        
        painter.setFont(QFont("Poppins", 10))
        painter.drawText(QRect(center.x() - radius, center.y() + 30, radius * 2, 30),
                        Qt.AlignCenter, "/ 100")

# =====================================================
# Main Dashboard Window
# =====================================================

class PostureDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Edge-Intelligent Real-Time Health & Postural Analytics")
        self.setGeometry(0, 0, 1920, 1080)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0F172A;
            }
            QLabel {
                color: #E2E8F0;
            }
        """)
        
        self.analyzer = PostureAnalyzer(30)
        self.video_thread = VideoCaptureThread(self.analyzer)
        self.video_thread.frame_ready.connect(self.on_frame_ready)
        
        self.setup_ui()
        self.video_thread.start()
        
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.current_fps = 0

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Main content (camera + analytics)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        # Left panel - Camera
        left_panel = self.create_camera_panel()
        content_layout.addWidget(left_panel, 2)
        
        # Right panel - Analytics
        right_panel = self.create_analytics_panel()
        content_layout.addWidget(right_panel, 1)
        
        main_layout.addLayout(content_layout, 1)
        
        # Bottom feedback
        bottom_panel = self.create_feedback_panel()
        main_layout.addWidget(bottom_panel)
        
        central_widget.setLayout(main_layout)

    def create_header(self):
        header_frame = RoundedFrame(radius=12)
        layout = QHBoxLayout()
        layout.setContentsMargins(30, 15, 30, 15)
        
        title = QLabel("Edge-Intelligent Health & Postural Analytics")
        title_font = QFont("Poppins", 24)
        title_font.setWeight(QFont.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #38BDF8;")
        
        layout.addWidget(title)
        layout.addStretch()
        
        # Edge AI badge
        edge_badge = QLabel("◎ Running Offline – Edge AI")
        badge_font = QFont("Poppins", 10)
        edge_badge.setFont(badge_font)
        edge_badge.setStyleSheet("color: #22C55E; padding: 8px 15px; background-color: rgba(34, 197, 94, 0.1); border-radius: 6px;")
        layout.addWidget(edge_badge)
        
        header_frame.setLayout(layout)
        return header_frame

    def create_camera_panel(self):
        camera_frame = RoundedFrame(radius=16)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(800, 600)
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setStyleSheet("border-radius: 16px; overflow: hidden;")
        
        layout.addWidget(self.camera_label)
        camera_frame.setLayout(layout)
        return camera_frame

    def create_analytics_panel(self):
        analytics_frame = QFrame()
        analytics_frame.setStyleSheet("background-color: transparent; border: none;")
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Status Card
        status_frame = RoundedFrame(radius=12)
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(25, 25, 25, 25)
        
        status_label = QLabel("Posture Status")
        status_label.setFont(QFont("Poppins", 11))
        status_label.setStyleSheet("color: rgba(226, 232, 240, 0.7);")
        
        self.status_value = QLabel("INITIALIZING")
        status_value_font = QFont("Poppins", 32)
        status_value_font.setWeight(QFont.Bold)
        self.status_value.setFont(status_value_font)
        self.status_value.setStyleSheet("color: #38BDF8;")
        
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.status_value)
        status_layout.addStretch()
        status_frame.setLayout(status_layout)
        layout.addWidget(status_frame)
        
        # Risk Score Card
        score_frame = RoundedFrame(radius=12)
        score_layout = QVBoxLayout()
        score_layout.setContentsMargins(25, 25, 25, 25)
        score_layout.setAlignment(Qt.AlignCenter)
        
        score_label = QLabel("Health Risk Score")
        score_label.setFont(QFont("Poppins", 11))
        score_label.setStyleSheet("color: rgba(226, 232, 240, 0.7);")
        score_layout.addWidget(score_label, alignment=Qt.AlignCenter)
        
        self.progress_widget = CircularProgressWidget()
        score_layout.addWidget(self.progress_widget, alignment=Qt.AlignCenter)
        
        score_frame.setLayout(score_layout)
        layout.addWidget(score_frame)
        
        # Duration Card
        duration_frame = RoundedFrame(radius=12)
        duration_layout = QVBoxLayout()
        duration_layout.setContentsMargins(20, 20, 20, 20)
        duration_layout.setSpacing(12)
        
        duration_label = QLabel("Posture Duration")
        duration_label.setFont(QFont("Poppins", 11))
        duration_label.setStyleSheet("color: rgba(226, 232, 240, 0.7);")
        duration_layout.addWidget(duration_label)
        
        # Good duration
        good_layout = QHBoxLayout()
        good_label = QLabel("✓ Good Posture")
        good_label.setFont(QFont("Poppins", 10))
        good_label.setStyleSheet("color: #22C55E;")
        self.good_time = QLabel("0s")
        self.good_time.setFont(QFont("Courier New", 12, QFont.Bold))
        self.good_time.setStyleSheet("color: #22C55E;")
        good_layout.addWidget(good_label)
        good_layout.addStretch()
        good_layout.addWidget(self.good_time)
        duration_layout.addLayout(good_layout)
        
        # Bad duration
        bad_layout = QHBoxLayout()
        bad_label = QLabel("⚠ Poor Posture")
        bad_label.setFont(QFont("Poppins", 10))
        bad_label.setStyleSheet("color: #EF4444;")
        self.bad_time = QLabel("0s")
        self.bad_time.setFont(QFont("Courier New", 12, QFont.Bold))
        self.bad_time.setStyleSheet("color: #EF4444;")
        bad_layout.addWidget(bad_label)
        bad_layout.addStretch()
        bad_layout.addWidget(self.bad_time)
        duration_layout.addLayout(bad_layout)
        
        duration_frame.setLayout(duration_layout)
        layout.addWidget(duration_frame)
        
        # FPS & System Info
        info_frame = RoundedFrame(radius=12)
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(20, 15, 20, 15)
        
        self.fps_label = QLabel("FPS: 0")
        self.fps_label.setFont(QFont("Courier New", 10))
        self.fps_label.setStyleSheet("color: rgba(226, 232, 240, 0.7);")
        
        camera_status = QLabel("📹 Camera Active")
        camera_status.setFont(QFont("Poppins", 10))
        camera_status.setStyleSheet("color: #22C55E;")
        
        info_layout.addWidget(self.fps_label)
        info_layout.addStretch()
        info_layout.addWidget(camera_status)
        info_frame.setLayout(info_layout)
        layout.addWidget(info_frame)
        
        layout.addStretch()
        analytics_frame.setLayout(layout)
        return analytics_frame

    def create_feedback_panel(self):
        feedback_frame = RoundedFrame(radius=12)
        layout = QHBoxLayout()
        layout.setContentsMargins(30, 25, 30, 25)
        
        feedback_icon = QLabel("💡")
        feedback_icon.setFont(QFont("Arial", 24))
        
        self.feedback_text = QLabel("Initializing system...")
        feedback_font = QFont("Poppins", 14)
        feedback_font.setWeight(QFont.Medium)
        self.feedback_text.setFont(feedback_font)
        self.feedback_text.setStyleSheet("color: #38BDF8;")
        
        layout.addWidget(feedback_icon)
        layout.addWidget(self.feedback_text, 1)
        layout.addStretch()
        
        feedback_frame.setLayout(layout)
        return feedback_frame

    def on_frame_ready(self, frame, data):
        self.frame_count += 1
        current_time = time.time()
        
        if current_time - self.fps_start_time >= 1:
            self.current_fps = self.frame_count
            self.frame_count = 0
            self.fps_start_time = current_time
            self.fps_label.setText(f"FPS: {self.current_fps}")
        
        # Draw skeleton on frame
        h, w = frame.shape[:2]
        if data['landmarks']:
            lm_data = data['landmarks']
            
            # Draw skeleton lines
            cv2.line(frame, lm_data['l_hip'], lm_data['l_shldr'], (255, 140, 0), 3)
            cv2.line(frame, lm_data['l_shldr'], lm_data['l_ear'], (255, 140, 0), 3)
            
            # Draw joints
            cv2.circle(frame, lm_data['l_hip'], 7, (34, 197, 94), -1)
            cv2.circle(frame, lm_data['l_shldr'], 7, (34, 197, 94), -1)
            cv2.circle(frame, lm_data['l_ear'], 7, (34, 197, 94), -1)
            
            # Draw angles
            cv2.putText(frame, f"Neck: {data['neck_angle']:.0f}°", 
                       (lm_data['l_ear'][0] + 20, lm_data['l_ear'][1] - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (56, 189, 248), 2)
            cv2.putText(frame, f"Torso: {data['torso_angle']:.0f}°",
                       (lm_data['l_hip'][0] + 20, lm_data['l_hip'][1] + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (56, 189, 248), 2)
        
        # Update status
        status = data['status']
        self.status_value.setText(status)
        
        if status == "GOOD":
            self.status_value.setStyleSheet("color: #22C55E;")
        elif status == "POOR":
            self.status_value.setStyleSheet("color: #FACC15;")
        elif status == "RISKY":
            self.status_value.setStyleSheet("color: #EF4444;")
        
        # Update score
        self.progress_widget.setValue(data['score'])
        
        # Update duration
        good_secs = self.analyzer.good_duration // 30
        bad_secs = self.analyzer.bad_duration // 30
        self.good_time.setText(f"{good_secs}s")
        self.bad_time.setText(f"{bad_secs}s")
        
        # Update feedback
        self.feedback_text.setText(data['message'])
        
        # Convert frame to QPixmap
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        convert_to_Qt = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(convert_to_Qt).scaledToWidth(800, Qt.SmoothTransformation)
        
        self.camera_label.setPixmap(pixmap)

    def closeEvent(self, event):
        self.video_thread.stop()
        self.video_thread.wait()
        event.accept()

# =====================================================
# Application Entry Point
# =====================================================

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dashboard = PostureDashboard()
    dashboard.show()
    sys.exit(app.exec_())
