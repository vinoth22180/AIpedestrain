from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class VerificationStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    UNCERTAIN = "UNCERTAIN"
    VERIFIED = "VERIFIED"
    STALE = "STALE"

class VerificationEventStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"

class HardwareEvidencePayload(BaseModel):
    """
    Contract for future ESP32 + MPU6050 physical traversal telemetry.
    No simulated values are generated now; this strictly defines the ingestion schema.
    """
    timestamp: Optional[str] = None
    edge_id: Optional[str] = None
    pitch_mean_deg: Optional[float] = None
    pitch_std_deg: Optional[float] = None
    roll_mean_deg: Optional[float] = None
    roll_std_deg: Optional[float] = None
    acc_x_rms: Optional[float] = None
    acc_y_rms: Optional[float] = None
    acc_z_rms: Optional[float] = None
    vibration_jerk_metric: Optional[float] = None
    traversal_duration_s: Optional[float] = None
    sample_count: Optional[int] = None
    device_id: Optional[str] = None
    signal_quality: Optional[float] = None

class EdgeEvidenceState(BaseModel):
    edge_id: str
    u: Any
    v: Any
    key: Any
    name: Optional[str] = None
    accessibility_confidence: float = 0.0
    accessibility_uncertainty: float = 1.0
    last_verified: Optional[str] = None
    observation_count: int = 0
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    missing_attributes: List[str] = Field(default_factory=list)
    known_attributes: Dict[str, Any] = Field(default_factory=dict)

class CounterfactualImpact(BaseModel):
    baseline_aoc: int = 0
    baseline_arl: float = 0.0
    counterfactual_aoc: int = 0
    counterfactual_arl: float = 0.0
    delta_aoc: int = 0
    delta_arl: float = 0.0
    mal_impact: float = 0.0
    cad: float = 0.0
    is_cut_edge: bool = False

class VerificationCandidate(BaseModel):
    edge_id: str
    u: Any
    v: Any
    key: Any
    name: str = ""
    priority_score: float = 0.0
    uncertainty: float = 0.0
    impact: CounterfactualImpact = Field(default_factory=CounterfactualImpact)
    reason: str = ""
    coordinates: Optional[List[List[float]]] = None

class ProbeSafeReturnResult(BaseModel):
    profile: str
    eligible: bool
    outbound_feasible: bool
    target_edge_feasible: bool
    return_feasible: bool
    reason: str
    outbound_distance_m: float = 0.0
    return_distance_m: float = 0.0
    travel_cost: float = 0.0

class ProbeSelectionResult(BaseModel):
    selected_probe: Optional[str] = None
    selection_reason: str = ""
    anchor_name: Optional[str] = None
    anchor_node: Optional[Any] = None
    anchor_coords: Optional[List[float]] = None
    eligible_probes: List[ProbeSafeReturnResult] = Field(default_factory=list)
    rejected_probes: List[ProbeSafeReturnResult] = Field(default_factory=list)

class VerificationEvent(BaseModel):
    event_id: str
    edge_id: str
    target_profile: str
    probe_profile: str
    anchor_node: Optional[Any] = None
    anchor_name: Optional[str] = None
    status: VerificationEventStatus = VerificationEventStatus.PENDING
    created_at: str
    updated_at: str
    notes: Optional[str] = None
    evidence: Optional[HardwareEvidencePayload] = None

class VerificationEventCreateRequest(BaseModel):
    edge_id: str
    target_profile: str = "wheelchair"
    probe_profile: str = "general"
    anchor_node: Optional[Any] = None
    notes: Optional[str] = None

class VerificationPlanResponse(BaseModel):
    target_profile: str
    selected_target: Optional[VerificationCandidate] = None
    probe_selection: Optional[ProbeSelectionResult] = None
    ranked_candidates: List[VerificationCandidate] = Field(default_factory=list)
    summary: str = ""
