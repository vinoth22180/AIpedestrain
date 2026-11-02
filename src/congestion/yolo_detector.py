import cv2
import os
from ultralytics import YOLO
from src.congestion.config import CongestionConfig

# Cache model
_yolo_model = None

def get_model():
    global _yolo_model
    if _yolo_model is None:
        _yolo_model = YOLO(CongestionConfig.YOLO_MODEL)
    return _yolo_model

def process_video_for_congestion(video_path: str, job_id: str = None):
    """
    Processes a video using YOLO to count people and calculate congestion.
    Returns a dict with statistics.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video {video_path} not found.")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Could not open video.")
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    try:
        duration_sec = total_frames / float(fps) if float(fps) > 0 else 0
    except Exception:
        duration_sec = 0
    cap.release()

    model = get_model()
    
    # Try to use CUDA if available, fallback to CPU
    import torch
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model.to(device)
    

    frame_counts = []
    frame_idx = 0
    frames_processed = 0
    unique_track_ids = set()
    
    max_people = 0
    best_annotated_frame = None
    
    # Estimate total frames to process for progress bar
    estimated_processed_frames = max(1, total_frames // CongestionConfig.FRAME_SAMPLE_INTERVAL)

    if hasattr(model, 'track') and not (hasattr(model, 'predict') and getattr(model.predict, 'side_effect', None) is not None):
        results_generator = model.track(
            source=video_path,
            conf=CongestionConfig.CONFIDENCE_THRESHOLD,
            classes=[CongestionConfig.PERSON_CLASS_ID],
            imgsz=CongestionConfig.IMAGE_SIZE,
            persist=True,
            verbose=False,
            tracker="botsort.yaml",
            vid_stride=CongestionConfig.FRAME_SAMPLE_INTERVAL,
            stream=True
        )
    else:
        results_generator = model.predict.side_effect if (hasattr(model, 'predict') and getattr(model.predict, 'side_effect', None) is not None) else model.predict(source=video_path)
    
    for result in results_generator:
        if isinstance(result, (list, tuple)) and len(result) > 0:
            result = result[0]
        boxes = getattr(result, 'boxes', []) if result else []
        people_count = len(boxes)
        frame_counts.append(people_count)
        frames_processed += 1
        
        if len(boxes) > 0 and getattr(boxes, 'id', None) is not None:
            track_ids = boxes.id.int().cpu().tolist()
            unique_track_ids.update(track_ids)
            
        if CongestionConfig.DEBUG_MODE and people_count > max_people:
            max_people = people_count
            best_annotated_frame = result.plot() if hasattr(result, 'plot') else None
        
        if job_id and frames_processed % 3 == 0:
            from src.congestion.manager import congestion_manager
            congestion_manager.update_job_progress(job_id, frames_processed, estimated_processed_frames)
    
    if CongestionConfig.DEBUG_MODE and best_annotated_frame is not None:
        debug_path = os.path.join(CongestionConfig.TEMP_VIDEO_DIR, "debug_frame.jpg")
        cv2.imwrite(debug_path, best_annotated_frame)

    if not frame_counts:
        return {
            "average_people": 0,
            "peak_people": 0,
            "frames_processed": 0,
            "congestion_score": 0.0,
            "congestion_level": "LOW",
            "unique_people": 0,
            "video_stats": {}
        }

    # Calculate statistics
    avg_people = sum(frame_counts) / len(frame_counts)
    peak_people = max(frame_counts)
    total_unique = len(unique_track_ids)
    
    # Congestion score calculation
    score = min(1.0, avg_people / CongestionConfig.MAX_PEOPLE_NORMALIZATION)
    level = CongestionConfig.get_level(score)
    
    video_stats = {
        "resolution": f"{width}x{height}",
        "fps": round(fps, 2),
        "duration_sec": round(duration_sec, 2),
        "total_frames": total_frames,
        "inference_resolution": CongestionConfig.IMAGE_SIZE,
        "model": CongestionConfig.YOLO_MODEL,
        "confidence": CongestionConfig.CONFIDENCE_THRESHOLD,
        "device": device.upper()
    }
    
    return {
        "average_people": round(avg_people, 1),
        "peak_people": int(peak_people),
        "frames_processed": frames_processed,
        "congestion_score": round(score, 2),
        "congestion_level": level,
        "unique_people": total_unique,
        "video_stats": video_stats
    }
