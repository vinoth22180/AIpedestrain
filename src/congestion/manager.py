import json
import time
from typing import Dict, List, Optional, Tuple
import math
import uuid
from pydantic import BaseModel

class CongestionState(BaseModel):
    location: str
    average_people: float
    peak_people: int
    congestion_score: float  # For backwards compatibility: reflects effective_score
    congestion_level: str    # For backwards compatibility: reflects effective_level
    timestamp: float = 0.0   # For backwards compatibility: reflects observed_at
    
    # Time-Aware Decay Fields
    observed_score: float = 0.0
    observed_level: str = "LOW"
    observed_at: float = 0.0
    effective_score: float = 0.0
    effective_level: str = "LOW"
    age_seconds: float = 0.0
    decay_half_life_seconds: float = 180.0
    decay_lambda: float = 0.0
    source: str = "uploaded_video"
    edge_ids: List[str] = []
    status: str = "active"  # "fresh", "aging", "expired"
    
    unique_people: Optional[int] = 0
    frames_processed: Optional[int] = 0
    video_stats: Optional[Dict] = {}

class CongestionManager:
    def __init__(self):
        # Maps location_id (e.g. "MGR" or "edge:1:2:k1") to its current congestion state
        self.current_state: Dict[str, CongestionState] = {}
        # Stores jobs in progress
        self.jobs: Dict[str, dict] = {}
        # History of congestion states per location
        self.history: Dict[str, List[CongestionState]] = {}
        self.MAX_HISTORY_POINTS = 50
        self._default_graph = None
        self._cached_graph_id: Optional[int] = None
        self._landmark_coords: Dict[str, Tuple[float, float]] = {}
        self._edge_coords: Dict[str, Tuple[float, float]] = {}
        self._node_coords: Dict[Any, Tuple[float, float]] = {}
        self._edge_id_to_edges: Dict[str, List[Tuple[Any, Any, Any]]] = {}

    def set_graph(self, G):
        self._default_graph = G
        self._build_index(G)

    def get_graph(self):
        if self._default_graph is None:
            try:
                from src.graph_manager import load_or_build_graph
                self._default_graph = load_or_build_graph()
            except Exception:
                pass
        return self._default_graph

    def _build_index(self, G):
        if G is None:
            return
        g_id = id(G)
        if self._cached_graph_id == g_id:
            return
        self._cached_graph_id = g_id
        self._landmark_coords.clear()
        self._edge_coords.clear()
        self._node_coords.clear()
        self._edge_id_to_edges.clear()

        # Load manual landmarks from JSON if available
        import os
        loc_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "vit_vellore", "processed", "vit_manual_locations.json"
        )
        if os.path.exists(loc_path):
            try:
                with open(loc_path, 'r') as f:
                    man_data = json.load(f)
                    for item in man_data.get('locations', []):
                        lon = float(item.get('longitude', 0))
                        lat = float(item.get('latitude', 0))
                        if lon and lat:
                            for key in [item.get('id'), item.get('name'), item.get('short_name')]:
                                if key:
                                    self._landmark_coords[str(key)] = (lon, lat)
            except Exception:
                pass

        # Index nodes
        for node, data in G.nodes(data=True):
            if 'x' in data and 'y' in data:
                coords = (float(data['x']), float(data['y']))
                self._node_coords[node] = coords
                self._node_coords[str(node)] = coords
                for attr_name in ['short_name', 'name', 'id', 'academic_block_id']:
                    val = data.get(attr_name)
                    if val:
                        self._landmark_coords[str(val)] = coords

        # Index edges
        edges_iter = G.edges(keys=True, data=True) if G.is_multigraph() else (
            (u, v, None, d) for u, v, d in G.edges(data=True)
        )
        for u, v, k, data in edges_iter:
            u_c = self._node_coords.get(u)
            v_c = self._node_coords.get(v)
            if u_c and v_c:
                mid = ((u_c[0] + v_c[0]) / 2.0, (u_c[1] + v_c[1]) / 2.0)
                e_id = data.get('edge_id')
                if e_id:
                    self._edge_coords[str(e_id)] = mid
                if k is not None:
                    self._edge_coords[str(k)] = mid
                    self._edge_coords[f"edge:{u}:{v}:{k}"] = mid
                    self._edge_coords[f"edge:{v}:{u}:{k}"] = mid
                self._edge_coords[(u, v)] = mid
                self._edge_coords[(v, u)] = mid
                self._edge_coords[(str(u), str(v))] = mid
                self._edge_coords[(str(v), str(u))] = mid

            e_key = str(data.get('edge_id') or k or f"edge:{u}:{v}")
            if e_key not in self._edge_id_to_edges:
                self._edge_id_to_edges[e_key] = []
            self._edge_id_to_edges[e_key].append((u, v, k))

    def is_valid_location(self, location: str, G=None) -> bool:
        if G is None:
            G = self.get_graph()
        if G is None:
            return True
        self._build_index(G)
        loc_str = str(location)
        if loc_str in self._landmark_coords or loc_str in self._edge_coords or loc_str in self._edge_id_to_edges:
            return True
        if loc_str.startswith("edge:"):
            parts = loc_str.split(":")
            if len(parts) >= 3:
                return True
        for node, data in G.nodes(data=True):
            if data.get('short_name') == location or data.get('name') == location:
                return True
        for u, v, d in G.edges(data=True):
            if d.get('edge_id') == location:
                return True
        return False

    def get_affected_edges(self, location: str, G) -> List[str]:
        if G is None:
            return [location]
        self._build_index(G)
        loc_coords = self._get_location_coords(location, G)
        affected = set()

        if location in self._edge_coords or location in self._edge_id_to_edges:
            affected.add(location)

        if loc_coords is not None:
            from src.congestion.config import CongestionConfig
            radius = CongestionConfig.OBSERVATION_RADIUS_METERS
            edges_iter = G.edges(keys=True, data=True) if G.is_multigraph() else (
                (u, v, None, d) for u, v, d in G.edges(data=True)
            )
            for u, v, k, data in edges_iter:
                e_id = data.get('edge_id') or (k if G.is_multigraph() else f"edge:{u}:{v}")
                u_c = self._node_coords.get(u)
                v_c = self._node_coords.get(v)
                if u_c and v_c:
                    mid_lon = (u_c[0] + v_c[0]) / 2.0
                    mid_lat = (u_c[1] + v_c[1]) / 2.0
                    dist = self._haversine(mid_lon, mid_lat, loc_coords[0], loc_coords[1])
                    if dist <= radius:
                        affected.add(str(e_id))

        return list(affected) if affected else [location]
        
    def create_job(self, location: str) -> str:
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {
            "job_id": job_id,
            "status": "processing",
            "location": location
        }
        return job_id

    def update_job(self, job_id: str, result: dict):
        if job_id in self.jobs:
            self.jobs[job_id].update(result)
            
            # Failed video processing must NOT refresh or update the observation timestamp or congestion
            if result.get("status") == "failed":
                self.jobs[job_id]["status"] = "failed"
                return

            self.jobs[job_id]["status"] = "completed"
            
            loc = self.jobs[job_id]["location"]
            
            # Use provided timestamp or current time
            ts = result.get("timestamp", 0.0)
            if ts == 0.0:
                ts = time.time()
                
            # Stale update protection:
            # Do not let an older video-processing job overwrite a newer observation
            # that was already accepted for the same edge.
            existing = self.current_state.get(loc)
            if existing and existing.observed_at > ts:
                return

            obs_score = float(result.get("congestion_score", 0.0))
            from src.congestion.config import CongestionConfig
            obs_level = CongestionConfig.normalize_level(result.get("congestion_level")) if result.get("congestion_level") else CongestionConfig.get_level(obs_score)
            
            half_life = float(result.get("decay_half_life_seconds", CongestionConfig.DECAY_HALF_LIFE_SECONDS))
            decay_lambda = CongestionConfig.get_decay_lambda(half_life)
            
            # Derive affected edge IDs:
            g_ref = self.get_graph()
            edge_ids = list(result.get("edge_ids", []))
            if not edge_ids:
                if g_ref is not None:
                    edge_ids = self.get_affected_edges(loc, g_ref)
                else:
                    edge_ids = [loc]
            elif g_ref is not None:
                extra = self.get_affected_edges(loc, g_ref)
                for eid in extra:
                    if eid not in edge_ids:
                        edge_ids.append(eid)
            
            # Create fresh state; replaces previous observation and resets decay period
            state = CongestionState(
                location=loc,
                average_people=result.get("average_people", 0),
                peak_people=result.get("peak_people", 0),
                congestion_score=obs_score,
                congestion_level=obs_level,
                timestamp=ts,
                observed_score=obs_score,
                observed_level=obs_level,
                observed_at=ts,
                effective_score=obs_score,
                effective_level=obs_level,
                age_seconds=0.0,
                decay_half_life_seconds=half_life,
                decay_lambda=round(decay_lambda, 6),
                source=result.get("source", "uploaded_video"),
                edge_ids=edge_ids,
                status="fresh",
                unique_people=result.get("unique_people", 0),
                frames_processed=result.get("frames_processed", 0),
                video_stats=result.get("video_stats", {})
            )
            self.current_state[loc] = state
            
            # Update history
            if loc not in self.history:
                self.history[loc] = []
            self.history[loc].append(state)
            
            # Bound history size
            if len(self.history[loc]) > self.MAX_HISTORY_POINTS:
                self.history[loc] = self.history[loc][-self.MAX_HISTORY_POINTS:]
            
    def update_job_progress(self, job_id: str, current: int, total: int):
        if job_id in self.jobs:
            self.jobs[job_id]["progress"] = {
                "current": current,
                "total": total,
                "percent": round(current / max(1, total) * 100)
            }

    def reset_congestion(self):
        self.current_state.clear()
        self.jobs.clear()
        self.history.clear()

    def get_job_status(self, job_id: str):
        return self.jobs.get(job_id)

    def get_effective_congestion(self, location: str, now: Optional[float] = None) -> Optional[CongestionState]:
        """
        Single source of truth for effective decayed congestion.
        C(t) = C0 * exp(-lambda * max(0, t - t0))
        """
        raw_state = self.current_state.get(location)
        if not raw_state:
            return None
            
        cur_time = time.time() if now is None else float(now)
        obs_at = raw_state.observed_at if raw_state.observed_at > 0 else raw_state.timestamp
        obs_score = raw_state.observed_score if raw_state.observed_score > 0 else raw_state.congestion_score
        from src.congestion.config import CongestionConfig
        obs_level = CongestionConfig.normalize_level(raw_state.observed_level or raw_state.congestion_level)
        
        # Elapsed time in seconds; cannot be negative
        elapsed_seconds = max(0.0, cur_time - obs_at)
        half_life = raw_state.decay_half_life_seconds or CongestionConfig.DECAY_HALF_LIFE_SECONDS
        decay_lambda = CongestionConfig.get_decay_lambda(half_life)
        
        # Exponential decay calculation (threshold < 0.1s to avoid microsecond precision drift)
        if decay_lambda > 0 and elapsed_seconds >= 0.1:
            effective_score = obs_score * math.exp(-decay_lambda * elapsed_seconds)
        else:
            effective_score = obs_score
            
        # Score never increases solely because time passed, and is non-negative
        effective_score = max(0.0, min(obs_score, effective_score))
        
        # Determine expiration & level
        is_expired = (
            elapsed_seconds > CongestionConfig.MAX_OBSERVATION_AGE_SECONDS or
            effective_score < CongestionConfig.EXPIRATION_THRESHOLD
        )
        
        if is_expired:
            status = "expired"
            effective_score = 0.0
            effective_level = "LOW"
        elif elapsed_seconds <= half_life:
            status = "fresh"
            effective_level = CongestionConfig.get_level(effective_score)
        else:
            status = "aging"
            effective_level = CongestionConfig.get_level(effective_score)
            
        edge_ids = raw_state.edge_ids if raw_state.edge_ids else [location]
        
        return CongestionState(
            location=raw_state.location,
            average_people=raw_state.average_people,
            peak_people=raw_state.peak_people,
            congestion_score=round(effective_score, 4),
            congestion_level=effective_level,
            timestamp=obs_at,
            observed_score=obs_score,
            observed_level=obs_level,
            observed_at=obs_at,
            effective_score=round(effective_score, 4),
            effective_level=effective_level,
            age_seconds=round(elapsed_seconds, 1),
            decay_half_life_seconds=half_life,
            decay_lambda=round(decay_lambda, 6),
            source=raw_state.source,
            edge_ids=edge_ids,
            status=status,
            unique_people=raw_state.unique_people,
            frames_processed=raw_state.frames_processed,
            video_stats=raw_state.video_stats
        )

    def get_active_congestion(self, now: Optional[float] = None) -> Dict[str, CongestionState]:
        """
        Returns active congestion states with decayed effective scores computed at time `now`.
        """
        res = {}
        for loc in list(self.current_state.keys()):
            eff = self.get_effective_congestion(loc, now=now)
            if eff:
                res[loc] = eff
        return res

    def get_history(self, location: str) -> List[CongestionState]:
        return self.history.get(location, [])

    def get_congestion_for_edge(self, u, v, G, now: Optional[float] = None) -> float:
        """
        Calculates if an edge falls within the observation radius of any congested location
        or directly matches an edge-based congestion observation.
        Returns the highest EFFECTIVE (decayed) congestion_score applicable.
        """
        if not self.current_state:
            return 0.0
            
        max_score = 0.0
        self._build_index(G)
        
        u_c = self._node_coords.get(u)
        v_c = self._node_coords.get(v)
        if u_c and v_c:
            mid_lon = (u_c[0] + v_c[0]) / 2.0
            mid_lat = (u_c[1] + v_c[1]) / 2.0
        elif isinstance(u, (tuple, list)) and len(u) >= 2 and isinstance(v, (tuple, list)) and len(v) >= 2:
            mid_lon = (u[0] + v[0]) / 2.0
            mid_lat = (u[1] + v[1]) / 2.0
        else:
            u_data = G.nodes.get(u, {})
            v_data = G.nodes.get(v, {})
            if 'x' in u_data and 'y' in u_data and 'x' in v_data and 'y' in v_data:
                mid_lon = (u_data['x'] + v_data['x']) / 2.0
                mid_lat = (u_data['y'] + v_data['y']) / 2.0
            else:
                mid_lon, mid_lat = None, None

        edge_data = G.get_edge_data(u, v)
        attrs = []
        if edge_data:
            attrs = list(edge_data.values()) if (isinstance(edge_data, dict) and G.is_multigraph()) else [edge_data]
        query_edge_ids = set()
        for attr in attrs:
            if isinstance(attr, dict) and attr.get('edge_id'):
                query_edge_ids.add(str(attr.get('edge_id')))
        
        for loc_id in list(self.current_state.keys()):
            eff_state = self.get_effective_congestion(loc_id, now=now)
            if not eff_state or eff_state.effective_score == 0.0:
                continue
                
            score = eff_state.effective_score
            e_ids = set(eff_state.edge_ids or [loc_id])
            e_ids.add(loc_id)
            
            # 1. Exact edge_id match (e.g. E001926 or matching any assigned edge_id)
            if query_edge_ids and query_edge_ids.intersection(e_ids):
                if score > max_score:
                    max_score = score
                continue

            # 2. Exact edge node-pair match (e.g. edge:1:2:k1)
            if loc_id.startswith("edge:"):
                parts = loc_id.split(":")
                if len(parts) >= 3:
                    state_u = parts[1]
                    state_v = parts[2]
                    # Compare as strings because node IDs can be int or str
                    if (str(u) == state_u and str(v) == state_v) or (str(u) == state_v and str(v) == state_u):
                        if score > max_score:
                            max_score = score
                continue

            # 3. Spatial proximity match
            loc_coords = self._get_location_coords(loc_id, G)
            if loc_coords and mid_lon is not None and mid_lat is not None:
                dist = self._haversine(mid_lon, mid_lat, loc_coords[0], loc_coords[1])
                from src.congestion.config import CongestionConfig
                if dist <= CongestionConfig.OBSERVATION_RADIUS_METERS:
                    if score > max_score:
                        max_score = score
                        
        return max_score

    def get_effective_level_for_edge(self, u, v, G, now: Optional[float] = None) -> str:
        """
        Returns the effective congestion level ('LOW', 'MEDIUM', 'HIGH')
        for the given edge (u, v) at timestamp 'now'.
        """
        score = self.get_congestion_for_edge(u, v, G, now=now)
        from src.congestion.config import CongestionConfig
        return CongestionConfig.get_level(score)

    def _get_location_coords(self, loc_id: str, G) -> Optional[Tuple[float, float]]:
        self._build_index(G)
        loc_str = str(loc_id)
        if loc_str in self._landmark_coords:
            return self._landmark_coords[loc_str]
        if loc_str in self._edge_coords:
            return self._edge_coords[loc_str]
        if loc_str.startswith("edge:"):
            parts = loc_str.split(":")
            if len(parts) >= 3:
                u_str, v_str = parts[1], parts[2]
                u_c = self._node_coords.get(u_str)
                v_c = self._node_coords.get(v_str)
                if u_c and v_c:
                    return ((u_c[0] + v_c[0]) / 2.0, (u_c[1] + v_c[1]) / 2.0)
        # Direct graph node search fallback
        for node, data in G.nodes(data=True):
            if data.get('short_name') == loc_id or data.get('name') == loc_id:
                return (data['x'], data['y'])
        return None

    @staticmethod
    def _haversine(lon1, lat1, lon2, lat2):
        R = 6371000 # radius of earth in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

congestion_manager = CongestionManager()

