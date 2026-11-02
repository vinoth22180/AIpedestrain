from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException
from typing import Optional
import os
import shutil

from src.congestion.manager import congestion_manager
from src.congestion.yolo_detector import process_video_for_congestion
from src.congestion.config import CongestionConfig

router = APIRouter(prefix="/api/congestion", tags=["congestion"])

def background_process_video(video_path: str, job_id: str):
    try:
        # Process the video
        result = process_video_for_congestion(video_path, job_id=job_id)
        # Update job with results
        congestion_manager.update_job(job_id, result)
    except Exception as e:
        print(f"Error processing video {job_id}: {e}")
        congestion_manager.update_job(job_id, {"status": "failed", "error": str(e)})
    finally:
        # Cleanup video file
        if os.path.exists(video_path):
            os.remove(video_path)

@router.post("/video")
async def upload_video(
    background_tasks: BackgroundTasks,
    location: str = Form(...),
    file: UploadFile = File(...)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
        
    if not congestion_manager.is_valid_location(location):
        raise HTTPException(
            status_code=400,
            detail=f"Location '{location}' cannot be resolved to a valid campus graph edge or landmark"
        )
        
    job_id = congestion_manager.create_job(location)
    file_path = os.path.join(CongestionConfig.TEMP_VIDEO_DIR, f"{job_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    background_tasks.add_task(background_process_video, file_path, job_id)
    return {"job_id": job_id, "status": "processing"}

@router.get("/status/{job_id}")
async def get_status(job_id: str):
    job = congestion_manager.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/active")
async def get_active_congestion(now: Optional[float] = None):
    """
    Returns time-aware active congestion states with both observed and decayed effective scores.
    Calculates effective score dynamically at request time using exponential decay.
    """
    states = congestion_manager.get_active_congestion(now=now)
    items = []
    for loc, state in states.items():
        items.append({
            "location": state.location,
            "edge_ids": state.edge_ids,
            "observed_score": state.observed_score,
            "observed_level": state.observed_level,
            "observed_at": state.observed_at,
            "effective_score": state.effective_score,
            "effective_level": state.effective_level,
            "congestion_score": state.effective_score,
            "congestion_level": state.effective_level,
            "age_seconds": state.age_seconds,
            "decay_half_life_seconds": state.decay_half_life_seconds,
            "decay_lambda": state.decay_lambda,
            "status": state.status,
            "source": state.source,
            "average_people": state.average_people,
            "peak_people": state.peak_people,
            "timestamp": state.observed_at
        })
    return {"active_congestions": items}

@router.get("/map")
async def get_congestion_map(now: Optional[float] = None):
    # Returns active congestion to display on frontend map with decayed effective scores
    state = congestion_manager.get_active_congestion(now=now)
    # Format for frontend
    result = []
    from src.congestion.prediction import calculate_trend_and_prediction
    for loc, data in state.items():
        history = congestion_manager.get_history(loc)
        prediction = calculate_trend_and_prediction(history)
        result.append({
            "location": data.location,
            "edge_ids": data.edge_ids,
            "average_people": data.average_people,
            "peak_people": data.peak_people,
            "congestion_score": data.effective_score,
            "congestion_level": data.effective_level,
            "observed_score": data.observed_score,
            "observed_level": data.observed_level,
            "observed_at": data.observed_at,
            "effective_score": data.effective_score,
            "effective_level": data.effective_level,
            "age_seconds": data.age_seconds,
            "decay_half_life_seconds": data.decay_half_life_seconds,
            "decay_lambda": data.decay_lambda,
            "status": data.status,
            "source": data.source,
            "prediction": prediction
        })
    return {"congested_areas": result}

@router.post("/reset")
async def reset_congestion():
    congestion_manager.reset_congestion()
    return {"status": "success", "message": "Congestion cleared"}


@router.get("/history/{location}")
async def get_congestion_history(location: str):
    history = congestion_manager.get_history(location)
    return {"location": location, "history": history}

@router.get("/trend/{location}")
async def get_congestion_trend(location: str):
    history = congestion_manager.get_history(location)
    from src.congestion.prediction import calculate_trend_and_prediction
    prediction = calculate_trend_and_prediction(history)
    return {"location": location, "prediction": prediction}
