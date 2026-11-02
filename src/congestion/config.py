import os

class CongestionConfig:
    # YOLO Settings
    YOLO_MODEL = "yolov8m.pt"
    CONFIDENCE_THRESHOLD = 0.25
    IMAGE_SIZE = 1024  # Balanced resolution for accuracy vs speed
    DEBUG_MODE = True  # Save annotated frame for verification
    FRAME_SAMPLE_INTERVAL = 8  # Process every Nth frame (approx 4 fps)
    PERSON_CLASS_ID = 0  # COCO class 0 is person

    # Congestion Score & Levels
    # Score = min(1.0, average_people / MAX_PEOPLE_NORMALIZATION)
    MAX_PEOPLE_NORMALIZATION = 40.0 

    # Configurable thresholds - Strict 3-level model
    THRESHOLDS = {
        "LOW": [0.00, 0.25],
        "MEDIUM": [0.25, 0.50],
        "HIGH": [0.50, 1.00],
        # Backward compatibility aliases
        "MODERATE": [0.25, 0.50],
        "SEVERE": [0.50, 1.00]
    }

    # Location to Graph mapping
    OBSERVATION_RADIUS_METERS = 50.0  # Proximity radius for landmark-based observations
    CONGESTION_WEIGHT = 1.0  # Mild baseline weight for tie-breaking allowed congestion; avoided levels are handled via staged A* search

    # Configurable Exponential Congestion Decay Settings
    # Half-life: Time in seconds for observation's influence to decay by 50%
    # With half_life = 180s (3 minutes), lambda = ln(2) / 180 ≈ 0.003851 s^-1
    DECAY_HALF_LIFE_SECONDS = 180.0
    # Threshold below which effective congestion is considered negligible / expired
    EXPIRATION_THRESHOLD = 0.02
    # Maximum age in seconds before an observation is considered expired
    MAX_OBSERVATION_AGE_SECONDS = 900.0  # 15 minutes

    # Storage
    TEMP_VIDEO_DIR = "temp_videos"

    @classmethod
    def get_decay_lambda(cls, half_life_seconds = None) -> float:
        """
        Derives decay rate (lambda, in inverse seconds s^-1) from configured half-life:
        lambda = ln(2) / half_life
        """
        import math
        hl = half_life_seconds if half_life_seconds is not None else cls.DECAY_HALF_LIFE_SECONDS
        if hl <= 0:
            return 0.0
        return math.log(2.0) / hl

    @classmethod
    def get_level(cls, score) -> str:
        """
        Classifies congestion score into one of three authoritative levels:
        - LOW:    0.00 <= score < 0.25
        - MEDIUM: 0.25 <= score < 0.50
        - HIGH:   0.50 <= score <= 1.00
        Clamps score to [0.0, 1.0] and handles None, non-finite, or invalid scores safely.
        """
        if score is None:
            return "LOW"
        try:
            val = float(score)
        except (ValueError, TypeError):
            return "LOW"
            
        import math
        if not math.isfinite(val):
            return "LOW"
            
        val = max(0.0, min(1.0, val))
        
        if val < 0.25:
            return "LOW"
        elif val < 0.50:
            return "MEDIUM"
        else:
            return "HIGH"

    @classmethod
    def normalize_level(cls, level_str: str) -> str:
        """
        Normalizes level strings to the authoritative 3-level model:
        Maps legacy 'SEVERE' to 'HIGH', 'MODERATE' to 'MEDIUM'.
        """
        if not level_str:
            return "LOW"
        s = str(level_str).upper().strip()
        if s == "SEVERE":
            return "HIGH"
        if s == "MODERATE":
            return "MEDIUM"
        if s in ("LOW", "MEDIUM", "HIGH"):
            return s
        return "LOW"

os.makedirs(CongestionConfig.TEMP_VIDEO_DIR, exist_ok=True)

