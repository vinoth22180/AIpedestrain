"""
Profile-Coupled Counterfactual Verification Controller (PCVC)
Closed-loop verification of uncertain pedestrian pathways on the VIT Vellore network.
"""

from src.pcvc.models import (
    VerificationStatus,
    VerificationEventStatus,
    EdgeEvidenceState,
    CounterfactualImpact,
    VerificationCandidate,
    ProbeSafeReturnResult,
    ProbeSelectionResult,
    VerificationEvent,
    VerificationEventCreateRequest,
    VerificationPlanResponse,
    HardwareEvidencePayload
)
from src.pcvc.uncertainty import (
    compute_edge_uncertainty,
    get_uncertain_edges,
    format_edge_id,
    parse_edge_id
)
from src.pcvc.counterfactual import evaluate_counterfactual_impact
from src.pcvc.probe_selector import (
    is_safe_probe,
    select_best_probe,
    find_nearest_landmark_anchor,
    get_vit_landmarks
)
from src.pcvc.evidence import evidence_tracker, EvidenceFreshnessTracker
from src.pcvc.controller import pcvc_controller, PCVCController

__all__ = [
    "VerificationStatus",
    "VerificationEventStatus",
    "EdgeEvidenceState",
    "CounterfactualImpact",
    "VerificationCandidate",
    "ProbeSafeReturnResult",
    "ProbeSelectionResult",
    "VerificationEvent",
    "VerificationEventCreateRequest",
    "VerificationPlanResponse",
    "HardwareEvidencePayload",
    "compute_edge_uncertainty",
    "get_uncertain_edges",
    "format_edge_id",
    "parse_edge_id",
    "evaluate_counterfactual_impact",
    "is_safe_probe",
    "select_best_probe",
    "find_nearest_landmark_anchor",
    "get_vit_landmarks",
    "evidence_tracker",
    "EvidenceFreshnessTracker",
    "pcvc_controller",
    "PCVCController"
]
