/* =====================================================
   APP STATE & CONFIGURATION
   ===================================================== */

const APP_STATE = {
    status: 'INITIALIZING',
    score: 0,
    goodDuration: 0,
    badDuration: 0,
    fps: 0,
    calibrated: false,
    calibrating: true,
    message: 'Initializing system...',
    lastUpdate: null
};

const CONFIG = {
    API_POLL_INTERVAL: 100,  // 100ms for real-time updates
    VIDEO_FEED_URL: '/api/video_feed',
    STATUS_API_URL: '/api/status',
    CALIBRATION_DURATION: 5000  // 5 seconds
};

/* =====================================================
   INITIALIZATION
   ===================================================== */

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Initializing Edge-AI Posture Dashboard');
    setupUI();
    startDataPolling();
});

function setupUI() {
    // Setup camera toggle button
    const cameraBtn = document.getElementById('cameraToggle');
    if (cameraBtn) {
        cameraBtn.addEventListener('click', toggleCamera);
    }
    
    console.log('✓ UI initialized');
}

/* =====================================================
   CAMERA CONTROL
   ===================================================== */

let cameraActive = true;

function toggleCamera() {
    cameraActive = !cameraActive;
    const btn = document.getElementById('cameraToggle');
    const videoWrapper = document.querySelector('.video-wrapper');
    const cameraOffOverlay = document.getElementById('cameraOffOverlay');
    const videoFeed = document.getElementById('videoFeed');
    
    if (cameraActive) {
        btn.classList.remove('camera-inactive');
        btn.classList.add('camera-active');
        btn.innerHTML = '<span class="btn-icon">🎥</span><span class="btn-label">Camera Active</span>';
        
        if (cameraOffOverlay) {
            cameraOffOverlay.classList.add('hidden');
        }
        
        // Restart video feed
        if (videoFeed) {
            videoFeed.src = CONFIG.VIDEO_FEED_URL + '?' + Date.now();
        }
        
        console.log('✓ Camera turned ON');
    } else {
        btn.classList.remove('camera-active');
        btn.classList.add('camera-inactive');
        btn.innerHTML = '<span class="btn-icon">📹</span><span class="btn-label">Camera Off</span>';
        
        if (cameraOffOverlay) {
            cameraOffOverlay.classList.remove('hidden');
        }
        
        console.log('✓ Camera turned OFF');
    }
}

/* =====================================================
   DATA POLLING - Real-time API Updates
   ===================================================== */

let pollInterval = null;

function startDataPolling() {
    console.log(`📊 Starting data polling (${CONFIG.API_POLL_INTERVAL}ms interval)`);
    
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(CONFIG.STATUS_API_URL);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            updateAppState(data);
            updateUI(data);
            
        } catch (error) {
            console.error('❌ API Error:', error);
            updateFeedback('⚠ Connection error - retrying...', 'error');
        }
    }, CONFIG.API_POLL_INTERVAL);
}

function updateAppState(data) {
    APP_STATE.status = data.status || 'INITIALIZING';
    APP_STATE.score = data.score || 0;
    APP_STATE.goodDuration = data.good_duration || 0;
    APP_STATE.badDuration = data.bad_duration || 0;
    APP_STATE.fps = data.fps || 0;
    APP_STATE.calibrated = data.calibrated || false;
    APP_STATE.calibrating = data.calibrating || false;
    APP_STATE.message = data.message || 'Processing...';
    APP_STATE.lastUpdate = new Date();
}

/* =====================================================
   UI UPDATES
   ===================================================== */

function updateUI(data) {
    updatePostureStatus();
    updateHealthScore();
    updateDurations();
    updateSystemInfo();
    updateCalibrationOverlay();
    updateFeedback();
}

/**
 * Update Posture Status Display
 */
function updatePostureStatus() {
    const statusValue = document.getElementById('statusValue');
    const statusBadge = document.getElementById('statusBadge');
    const statusMessage = document.getElementById('statusMessage');
    
    if (!statusValue || !statusBadge || !statusMessage) return;
    
    let displayStatus = APP_STATE.status;
    let statusClass = APP_STATE.status.toLowerCase();
    
    // Handle special states
    if (APP_STATE.calibrating) {
        displayStatus = 'CALIBRATING';
        statusClass = 'calibrating';
    } else if (APP_STATE.status === 'INITIALIZING') {
        displayStatus = '—';
        statusClass = 'initializing';
    }
    
    // Update display
    statusValue.textContent = displayStatus;
    statusValue.className = `status-value ${statusClass}`;
    
    statusBadge.textContent = displayStatus;
    statusBadge.className = `status-badge ${statusClass}`;
    
    statusMessage.textContent = APP_STATE.message;
    
    // Apply border glow based on status
    applyBorderGlow(statusValue, statusClass);
}

/**
 * Update Health Risk Score with smooth animation
 */
function updateHealthScore() {
    const scoreNumber = document.getElementById('scoreNumber');
    const scoreRing = document.getElementById('scoreRing');
    
    if (!scoreNumber || !scoreRing) return;
    
    // Update number
    scoreNumber.textContent = Math.round(APP_STATE.score);
    
    // Calculate circumference and offset for smooth ring animation
    const radius = 50;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (APP_STATE.score / 100) * circumference;
    
    scoreRing.style.strokeDashoffset = offset;
    
    // Update color based on score
    scoreRing.className = 'score-ring';
    if (APP_STATE.score < 40) {
        scoreRing.classList.add('good');
    } else if (APP_STATE.score < 70) {
        scoreRing.classList.add('poor');
    } else {
        scoreRing.classList.add('risky');
    }
}

/**
 * Update Good/Poor Duration displays
 */
function updateDurations() {
    const goodDuration = document.getElementById('goodDuration');
    const badDuration = document.getElementById('badDuration');
    
    if (goodDuration) {
        goodDuration.textContent = `${APP_STATE.goodDuration}s`;
    }
    
    if (badDuration) {
        badDuration.textContent = `${APP_STATE.badDuration}s`;
    }
}

/**
 * Update FPS and System Status
 */
function updateSystemInfo() {
    const fpsValue = document.getElementById('fpsValue');
    const systemStatus = document.getElementById('systemStatus');
    
    if (fpsValue) {
        fpsValue.textContent = `${APP_STATE.fps}`;
    }
    
    if (systemStatus) {
        systemStatus.textContent = cameraActive ? '● Online' : '● Offline';
        systemStatus.style.color = cameraActive ? '#22c55e' : '#94a3b8';
    }
}

/**
 * Update Calibration Overlay
 */
function updateCalibrationOverlay() {
    const overlay = document.getElementById('calibrationOverlay');
    const badge = document.getElementById('calibrationBadge');
    
    if (!overlay || !badge) return;
    
    if (APP_STATE.calibrating) {
        overlay.classList.remove('hidden');
        badge.classList.add('hidden');
        
        // Calculate and update calibration progress
        const startTime = APP_STATE.lastCalibrationStart || Date.now();
        const elapsed = Date.now() - startTime;
        const progress = Math.min(100, Math.round((elapsed / CONFIG.CALIBRATION_DURATION) * 100));
        
        const progressFill = document.getElementById('calProgressFill');
        const calPercent = document.getElementById('calPercent');
        
        if (progressFill) {
            progressFill.style.width = `${progress}%`;
        }
        
        if (calPercent) {
            calPercent.textContent = `${progress}%`;
        }
        
        if (!APP_STATE.lastCalibrationStart) {
            APP_STATE.lastCalibrationStart = startTime;
        }
    } else {
        overlay.classList.add('hidden');
        badge.classList.remove('hidden');
    }
}

/**
 * Update Feedback Message
 */
function updateFeedback(message = null, type = 'info') {
    const feedbackText = document.getElementById('feedbackMessage');
    const feedbackFooter = document.querySelector('.feedback-footer');
    
    if (!feedbackText) return;
    
    let displayMessage = message || APP_STATE.message || 'System running...';
    feedbackText.textContent = displayMessage;
    
    // Color code based on status
    if (type === 'error') {
        feedbackText.style.color = '#ef4444';
    } else if (APP_STATE.status === 'GOOD') {
        feedbackText.style.color = '#22c55e';
    } else if (APP_STATE.status === 'POOR') {
        feedbackText.style.color = '#facc15';
    } else if (APP_STATE.status === 'RISKY') {
        feedbackText.style.color = '#ef4444';
    } else {
        feedbackText.style.color = '#94a3b8';
    }
}

/**
 * Apply border glow effect based on posture status
 */
function applyBorderGlow(element, status) {
    if (!element) return;
    
    let glowColor = 'rgba(56, 189, 248, 0.5)';  // Blue for initializing
    
    switch (status.toLowerCase()) {
        case 'good':
            glowColor = 'rgba(34, 197, 94, 0.5)';  // Green
            break;
        case 'poor':
            glowColor = 'rgba(250, 204, 21, 0.5)';  // Amber
            break;
        case 'risky':
            glowColor = 'rgba(239, 68, 68, 0.5)';  // Red
            break;
    }
    
    element.style.textShadow = `0 0 20px ${glowColor}`;
}

/* =====================================================
   VIDEO FEED MONITORING
   ===================================================== */

document.addEventListener('DOMContentLoaded', () => {
    const videoFeed = document.getElementById('videoFeed');
    
    if (videoFeed) {
        videoFeed.addEventListener('load', () => {
            console.log('✓ Video feed loaded');
        });
        
        videoFeed.addEventListener('error', () => {
            console.warn('⚠ Video feed error');
            updateFeedback('⚠ Camera feed error', 'error');
        });
    }
});

/* =====================================================
   LOGGING & DEBUGGING
   ===================================================== */

console.log('📊 Edge-AI Posture Dashboard - Ready');
console.log('🔗 API Endpoints:');
console.log('   - Status: ' + CONFIG.STATUS_API_URL);
console.log('   - Video: ' + CONFIG.VIDEO_FEED_URL);
console.log('⚙️ Config:');
console.log('   - Poll Interval: ' + CONFIG.API_POLL_INTERVAL + 'ms');
console.log('   - Calibration Duration: ' + CONFIG.CALIBRATION_DURATION + 'ms');
