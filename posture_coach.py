import cv2
import time
import math as m
import mediapipe as mp
from collections import deque

# =====================================================
# Utility Functions (UNCHANGED LOGIC)
# =====================================================

def findDistance(x1, y1, x2, y2):
    return m.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

def findAngle(x1, y1, x2, y2):
    theta = m.acos((y2 - y1) * (-y1) /
                   (m.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) * y1))
    return int(180 / m.pi) * theta

# =====================================================
# Posture Analyzer Class (EDGE AI CORE)
# =====================================================

class PostureAnalyzer:
    def __init__(self, fps):
        self.fps = fps
        self.good_frames = 0
        self.bad_frames = 0

        self.calibrated = False
        self.calibration_frames = int(4 * fps)
        self.neck_base = []
        self.torso_base = []

        self.score_buffer = deque(maxlen=10)

    def calibrate(self, neck_angle, torso_angle):
        self.neck_base.append(neck_angle)
        self.torso_base.append(torso_angle)

        if len(self.neck_base) >= self.calibration_frames:
            self.base_neck = sum(self.neck_base) / len(self.neck_base)
            self.base_torso = sum(self.torso_base) / len(self.torso_base)
            self.calibrated = True

    def analyze(self, neck_angle, torso_angle):
        neck_diff = abs(neck_angle - self.base_neck)
        torso_diff = abs(torso_angle - self.base_torso)

        # Original posture logic preserved
        if neck_angle < 40 and torso_angle < 10:
            self.good_frames += 1
            self.bad_frames = 0
            raw_score = 10
            status = "GOOD"
            message = "Great posture! Keep it up 👍"
        else:
            self.bad_frames += 1
            self.good_frames = 0
            raw_score = min(100, neck_diff * 2 + torso_diff * 3)
            status = "POOR" if raw_score < 60 else "RISKY"
            message = "Straighten your back and neck!"

        self.score_buffer.append(raw_score)
        smooth_score = int(sum(self.score_buffer) / len(self.score_buffer))

        return status, smooth_score, message

# =====================================================
# Visualization Utilities
# =====================================================

def draw_ui(image, status, score, message, color):
    h, w = image.shape[:2]

    cv2.rectangle(image, (0, 0), (w, 80), (30, 30, 30), -1)
    cv2.putText(image, f"Posture Status : {status}", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
    cv2.putText(image, f"Health Risk Score : {score}/100", (20, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    cv2.rectangle(image, (0, h - 50), (w, h), (30, 30, 30), -1)
    cv2.putText(image, message, (20, h - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

# =====================================================
# MAIN EDGE AI PIPELINE
# =====================================================

mp_pose = mp.solutions.pose
pose = mp_pose.Pose()

cap = cv2.VideoCapture(0)
fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30

analyzer = PostureAnalyzer(fps)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    h, w = frame.shape[:2]

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = pose.process(rgb)
    frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    if result.pose_landmarks:
        lm = result.pose_landmarks.landmark
        PL = mp_pose.PoseLandmark

        l_shldr = (int(lm[PL.LEFT_SHOULDER].x * w),
                   int(lm[PL.LEFT_SHOULDER].y * h))
        r_shldr = (int(lm[PL.RIGHT_SHOULDER].x * w),
                   int(lm[PL.RIGHT_SHOULDER].y * h))
        l_ear = (int(lm[PL.LEFT_EAR].x * w),
                 int(lm[PL.LEFT_EAR].y * h))
        l_hip = (int(lm[PL.LEFT_HIP].x * w),
                 int(lm[PL.LEFT_HIP].y * h))

        neck_angle = findAngle(l_shldr[0], l_shldr[1], l_ear[0], l_ear[1])
        torso_angle = findAngle(l_hip[0], l_hip[1], l_shldr[0], l_shldr[1])

        if not analyzer.calibrated:
            analyzer.calibrate(neck_angle, torso_angle)
            cv2.putText(frame, "Calibrating posture... Sit straight",
                        (20, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1,
                        (0, 255, 255), 3)
        else:
            status, score, msg = analyzer.analyze(neck_angle, torso_angle)
            color = (0, 255, 0) if status == "GOOD" else (0, 165, 255) if status == "POOR" else (0, 0, 255)
            draw_ui(frame, status, score, msg, color)

        # Skeleton & angle lines
        cv2.line(frame, l_shldr, l_ear, (255, 0, 0), 3)
        cv2.line(frame, l_hip, l_shldr, (255, 0, 0), 3)
        cv2.circle(frame, l_shldr, 6, (0, 255, 0), -1)
        cv2.circle(frame, l_ear, 6, (0, 255, 0), -1)
        cv2.circle(frame, l_hip, 6, (0, 255, 0), -1)

    cv2.imshow("Edge AI Posture Coach", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
