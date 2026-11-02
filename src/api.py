from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Any
import os
import json
import math

from src.graph_manager import load_or_build_graph
from src.pada_r.router import compute_pada_route
from src.config.loader import DATASETS_CONFIG
from src.darr.router import compute_darr_routes
from src.weather.service import weather_service
from src.congestion.api import router as congestion_router
import time

app = FastAPI(title="Dynamic Accessibility Resilience Routing (DARR) API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(congestion_router)

G_base = None

@app.get("/api/config")
def get_config():
    active_dataset = DATASETS_CONFIG.get("active", "vit_vellore")
    return DATASETS_CONFIG.get("datasets", {}).get(active_dataset, {})

@app.on_event("startup")
def startup_event():
    global G_base
    print("Initializing Graph on startup...")
    G_base = load_or_build_graph()
    from src.congestion.manager import congestion_manager
    congestion_manager.set_graph(G_base)
    print("Graph initialized successfully.")

class RouteRequest(BaseModel):
    origin: List[float]
    destination: List[float]
    profile: str = "general"
    active_route_path: Optional[List[Any]] = None
    bypass_stability: bool = False
    now: Optional[float] = None

@app.post("/api/route")
def get_route(request: RouteRequest):
    if G_base is None:
        raise HTTPException(status_code=503, detail="Graph not loaded yet")
        
    origin_tuple = (request.origin[0], request.origin[1])
    dest_tuple = (request.destination[0], request.destination[1])
    
    path, path_edges, route_status, route_explanation, stats, candidates = compute_pada_route(
        G_base, origin_tuple, dest_tuple, request.profile,
        active_route_path=request.active_route_path,
        bypass_stability=request.bypass_stability,
        now=request.now
    )
    
    if not path or not path_edges:
        detail_msg = "No accessible path found between these locations"
        if isinstance(route_explanation, dict) and route_explanation.get('reason'):
            detail_msg = route_explanation['reason']
        elif isinstance(route_explanation, str):
            detail_msg = route_explanation
        raise HTTPException(status_code=404, detail=detail_msg)
        
    route_coords = []
    restricted_segments = []
    
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        edge = path_edges[i]
        geom = edge.get('geometry')
        if geom is None or not hasattr(geom, 'coords'):
            continue
        coords = list(geom.coords)
        u_data = G_base.nodes.get(u, {})
        v_data = G_base.nodes.get(v, {})
        if 'x' in u_data and 'y' in u_data and 'x' in v_data and 'y' in v_data:
            d_start_u = math.hypot(coords[0][0] - u_data['x'], coords[0][1] - u_data['y'])
            d_start_v = math.hypot(coords[0][0] - v_data['x'], coords[0][1] - v_data['y'])
            if d_start_v < d_start_u:
                coords = list(reversed(coords))
        route_coords.extend(coords)
        
        slope_val = edge.get('slope_percent')
        try:
            slope_val = float(slope_val) if slope_val is not None else 0.0
        except (ValueError, TypeError):
            slope_val = 0.0
            
        has_stairs = edge.get('stairs', False) or edge.get('highway') == 'steps'
        is_wc_inaccessible = edge.get('wheelchair_accessible') is False or edge.get('wheelchair') == 'no'
        has_barrier = edge.get('barrier') not in ('no', 'none', 'unknown', False, None)
        is_steep = slope_val > 8.0
        
        is_restricted = has_stairs or is_wc_inaccessible or has_barrier or is_steep
        if is_restricted:
            restricted_segments.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords
                },
                "properties": {
                    "cost": edge.get('cost', 0),
                    "stairs": has_stairs,
                    "wheelchair_accessible": edge.get('wheelchair_accessible'),
                    "slope_percent": slope_val,
                    "barrier": edge.get('barrier'),
                    "cost_breakdown": edge.get('cost_breakdown', {})
                }
            })

    geojson_route = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": route_coords
        },
        "properties": {
            "profile": request.profile,
            "total_cost": stats['cost']
        }
    }
    
    # Route-specific congestion metadata computed directly from the selected route's edges
    route_summary = stats.get('accessibility_summary', {})
    route_cong_score = route_summary.get('max_congestion_score', 0.0)
    route_cong_level = route_summary.get('max_congestion_level', 'LOW')

    return {
        "algorithm": "A* (Profile-Aware Pedestrian Routing)",
        "route_status": route_status,
        "profile": request.profile,
        "route_explanation": route_explanation,
        "route": geojson_route,
        "restricted_segments": {
            "type": "FeatureCollection",
            "features": restricted_segments
        },
        "accessibility_summary": stats.get('accessibility_summary', {}),
        "accessibility": stats.get('accessibility', {}),
        "stats": stats,
        "candidate_routes": candidates,
        "selected_candidate": candidates[0] if candidates else None,
        "network_resilience": None,
        "collapse_risk": None,
        "decision_summary": route_explanation.get('reason', '') if isinstance(route_explanation, dict) else str(route_explanation),
        "congestion_score": route_cong_score,
        "congestion_level": route_cong_level,
        "diagnostics": stats.get('diagnostics', {})
    }

@app.get("/api/sensors")
def get_sensors():
    return []

@app.get("/api/signals")
def get_signals():
    return []

@app.get("/api/profiles")
def get_profiles():
    from src.pada_r.profiles import PROFILE_DESCRIPTIONS, PROFILE_CONGESTION_MULTIPLIERS, PREGNANT_MAX_SLOPE, WHEELCHAIR_MAX_SLOPE, ELDERLY_SLOPE_THRESHOLD
    return {
        "profiles": PROFILE_DESCRIPTIONS,
        "thresholds": {
            "pregnant_max_slope": PREGNANT_MAX_SLOPE,
            "wheelchair_max_slope": WHEELCHAIR_MAX_SLOPE,
            "elderly_slope_threshold": ELDERLY_SLOPE_THRESHOLD,
            "congestion_multipliers": PROFILE_CONGESTION_MULTIPLIERS
        }
    }

@app.get("/api/weather")
def get_weather():
    return weather_service.get_current_weather()

@app.get("/api/landmarks")
def get_landmarks():
    import os
    import json
    processed_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vit_vellore", "processed")
    path = os.path.join(processed_dir, "vit_manual_locations.json")
    results = []
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
            for loc in data.get('locations', []):
                results.append({
                    "name": loc['name'],
                    "coords": [loc['longitude'], loc['latitude']]
                })
    return results

@app.get("/api/academic_blocks")
def get_academic_blocks():
    import os
    import json
    processed_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vit_vellore", "processed")
    path = os.path.join(processed_dir, "vit_manual_locations.json")
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
        features = []
        for loc in data.get('locations', []):
            if loc.get('type') == 'academic_block':
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [loc['longitude'], loc['latitude']]
                    },
                    "properties": {
                        "name": loc['name'],
                        "short_name": loc['short_name'],
                        "id": loc['id']
                    }
                })
        return {"type": "FeatureCollection", "features": features}
    return {"type": "FeatureCollection", "features": []}

@app.get("/api/pedestrian_network/stats")
def get_pedestrian_network_stats():
    if G_base is None:
        return {}
    
    stairs = 0
    ramps = 0
    crossings = 0
    barriers = 0
    slopes = 0
    subways = 0
    
    for u, v, d in G_base.edges(data=True):
        if d.get("stairs"): stairs += 1
        if d.get("ramp"): ramps += 1
        if d.get("crossing") and d.get("crossing") != "no": crossings += 1
        if d.get("barrier") and d.get("barrier") != "no": barriers += 1
        if d.get("subway"): subways += 1
        
        status = d.get("slope_status")
        percent = d.get("slope_percent")
        if status in ["up", "down"]:
            slopes += 1
        elif status == "measured" and percent is not None and percent > 4:
            slopes += 1
            
    return {
        "stairs": stairs,
        "ramps": ramps,
        "crossings": crossings,
        "barriers": barriers,
        "slopes": slopes,
        "subways": subways
    }

@app.get("/api/pedestrian_network")
def get_pedestrian_network():
    if G_base is None:
        return {"type": "FeatureCollection", "features": []}
        
    features = []
    for u, v, k, d in G_base.edges(keys=True, data=True):
        geom = d.get('geometry')
        if not geom: continue
        
        props = dict(d)
        if 'geometry' in props:
            del props['geometry']
            
        name = props.get('name')
        if name:
            props['display_name'] = name
        else:
            u_block = G_base.nodes[u].get('academic_block_id')
            v_block = G_base.nodes[v].get('academic_block_id')
            
            if u_block and v_block and u_block != v_block:
                props['display_name'] = f"{u_block}_to_{v_block}_Walkway"
            elif u_block and props.get('stairs'):
                props['display_name'] = f"{u_block} Stairs"
            elif v_block and props.get('stairs'):
                props['display_name'] = f"{v_block} Stairs"
            elif props.get('stairs'):
                props['display_name'] = "STAIRS"
            elif props.get('ramp'):
                props['display_name'] = "RAMP"
            else:
                props['display_name'] = None
                
        edge_id = props.get("edge_id")
        if not edge_id:
            edge_id = f"edge:{u}:{v}:{k}"
            
        clean_props = {
            "edge_id": edge_id,
            "name": props.get("name"),
            "display_name": props.get("display_name"),
            "stairs": props.get("stairs", False),
            "ramp": props.get("ramp", False),
            "highway": props.get("highway"),
            "slope_percent": props.get("slope_percent"),
            "slope_status": props.get("slope_status"),
            "barrier": props.get("barrier"),
            "crossing": props.get("crossing"),
            "subway": props.get("subway", False)
        }
                
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": list(geom.coords)
            },
            "properties": clean_props
        })
        
    return {"type": "FeatureCollection", "features": features}

@app.post("/api/routes/candidates")
def get_candidate_routes(request: RouteRequest):
    if G_base is None:
        raise HTTPException(status_code=503, detail="Graph not loaded yet")
        
    origin_tuple = (request.origin[0], request.origin[1])
    dest_tuple = (request.destination[0], request.destination[1])
    
    path, path_edges, route_status, route_explanation, stats, candidates = compute_pada_route(
        G_base, origin_tuple, dest_tuple, request.profile, now=request.now
    )
    if not path:
        detail_msg = "No accessible route found"
        if isinstance(route_explanation, dict) and route_explanation.get('reason'):
            detail_msg = route_explanation['reason']
        raise HTTPException(status_code=404, detail=detail_msg)
        
    return {
        "status": "SUCCESS",
        "algorithm": "A*",
        "profile": request.profile,
        "selected_route": candidates[0] if candidates else None,
        "candidate_routes": candidates,
        "network_resilience": None,
        "collapse_risk": None,
        "decision_summary": route_explanation.get('reason', '')
    }

