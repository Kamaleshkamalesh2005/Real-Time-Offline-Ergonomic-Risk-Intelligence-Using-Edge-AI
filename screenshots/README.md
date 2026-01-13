# Screenshots Directory

This directory contains screenshots of the application in action.

## Required Screenshots

Please add the following screenshots to this directory:

1. **dashboard-main.png** - Main dashboard view with all components
2. **calibration.png** - Calibration process with progress indicator
3. **good-posture.png** - System showing good posture detection (green status)
4. **poor-posture.png** - System showing poor/risky posture (red/amber status)
5. **analytics.png** - Analytics view with metrics and duration tracking

## Guidelines for Screenshots

- **Resolution**: Minimum 1920x1080 (Full HD)
- **Format**: PNG or JPG
- **Quality**: High quality, clear and readable
- **Content**: Show the application in use with actual posture detection
- **Lighting**: Good lighting conditions for clear visibility

## How to Capture

### For Web Dashboard (server.py)
1. Run `python server.py`
2. Open http://localhost:5000 in browser
3. Allow camera access
4. Wait for calibration to complete
5. Take screenshots at different states (good posture, poor posture, etc.)

### For Desktop Application (dashboard.py)
1. Run `python dashboard.py`
2. Allow camera access
3. Wait for calibration to complete
4. Take screenshots using your OS screenshot tool

### For CLI Mode (posture_coach.py)
1. Run `python posture_coach.py`
2. Wait for calibration
3. Take screenshots of the OpenCV window

## Naming Convention

Use lowercase with hyphens:
- ✅ `dashboard-main.png`
- ✅ `good-posture.png`
- ❌ `Dashboard Main.PNG`
- ❌ `goodPosture.jpg`
