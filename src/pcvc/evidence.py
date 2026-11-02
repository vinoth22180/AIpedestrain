import math
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from src.pcvc.models import (
    VerificationEvent,
    VerificationEventStatus,
    VerificationStatus,
    HardwareEvidencePayload
)

class EvidenceFreshnessTracker:
    """
    Manages physical verification observation freshness and verification events.
    Completely separate from the traffic/congestion Signal Decay engine.
    Uses exponential decay: freshness(t) = exp(-lambda_evidence * delta_t)
    """

    def __init__(self, lambda_evidence: float = 0.0001, stale_threshold: float = 0.4):
        # Default lambda: half-life ~ 2 hours (6930 seconds)
        self.lambda_evidence = lambda_evidence
        self.stale_threshold = stale_threshold
        # edge_id -> { "last_verified_ts": float, "observation_count": int, "latest_evidence": Optional[HardwareEvidencePayload] }
        self.edge_observations: Dict[str, Dict[str, Any]] = {}
        # event_id -> VerificationEvent
        self.events: Dict[str, VerificationEvent] = {}

    def create_verification_event(
        self,
        edge_id: str,
        target_profile: str,
        probe_profile: str,
        anchor_node: Optional[Any] = None,
        anchor_name: Optional[str] = None,
        notes: Optional[str] = None
    ) -> VerificationEvent:
        """Creates and logs a new verification event in PENDING state."""
        event_id = f"VE-{uuid.uuid4().hex[:8].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()

        event = VerificationEvent(
            event_id=event_id,
            edge_id=edge_id,
            target_profile=target_profile,
            probe_profile=probe_profile,
            anchor_node=anchor_node,
            anchor_name=anchor_name,
            status=VerificationEventStatus.PENDING,
            created_at=now_iso,
            updated_at=now_iso,
            notes=notes,
            evidence=None
        )
        self.events[event_id] = event
        return event

    def get_event(self, event_id: str) -> Optional[VerificationEvent]:
        return self.events.get(event_id)

    def list_events(self, limit: int = 50) -> List[VerificationEvent]:
        # Return sorted by created_at descending
        return sorted(self.events.values(), key=lambda e: e.created_at, reverse=True)[:limit]

    def update_event_status(
        self,
        event_id: str,
        status: VerificationEventStatus,
        evidence: Optional[HardwareEvidencePayload] = None,
        notes: Optional[str] = None
    ) -> Optional[VerificationEvent]:
        """Updates event status and optionally attaches future hardware evidence."""
        if event_id not in self.events:
            return None
        event = self.events[event_id]
        event.status = status
        event.updated_at = datetime.now(timezone.utc).isoformat()
        if evidence is not None:
            event.evidence = evidence
        if notes:
            event.notes = notes

        if status == VerificationEventStatus.COMPLETED:
            self.record_observation(event.edge_id, evidence=evidence)

        return event

    def record_observation(
        self,
        edge_id: str,
        timestamp: Optional[float] = None,
        evidence: Optional[HardwareEvidencePayload] = None
    ) -> None:
        """
        Records a physical verification observation for an edge.
        Resets freshness to 1.0 at timestamp.
        """
        ts = timestamp if timestamp is not None else time.time()
        record = self.edge_observations.get(edge_id, {
            "last_verified_ts": ts,
            "observation_count": 0,
            "latest_evidence": None
        })
        record["last_verified_ts"] = ts
        record["observation_count"] += 1
        if evidence is not None:
            record["latest_evidence"] = evidence
        self.edge_observations[edge_id] = record

    def get_freshness(self, edge_id: str, current_time: Optional[float] = None) -> float:
        """
        Calculates observation freshness: freshness(t) = exp(-lambda * delta_t).
        Returns 0.0 if the edge has never been verified.
        """
        if edge_id not in self.edge_observations:
            return 0.0
        ts = self.edge_observations[edge_id]["last_verified_ts"]
        now = current_time if current_time is not None else time.time()
        delta_t = max(0.0, now - ts)
        return round(math.exp(-self.lambda_evidence * delta_t), 4)

    def get_verification_status(self, edge_id: str, current_time: Optional[float] = None) -> VerificationStatus:
        """Determines current status: UNKNOWN, UNCERTAIN, VERIFIED, or STALE."""
        if edge_id not in self.edge_observations:
            return VerificationStatus.UNKNOWN
        freshness = self.get_freshness(edge_id, current_time)
        if freshness >= self.stale_threshold:
            return VerificationStatus.VERIFIED
        return VerificationStatus.STALE

    def get_observation_summary(self, edge_id: str) -> Dict[str, Any]:
        obs = self.edge_observations.get(edge_id)
        if not obs:
            return {
                "verified": False,
                "freshness": 0.0,
                "status": VerificationStatus.UNKNOWN.value,
                "observation_count": 0,
                "last_verified_ts": None
            }
        freshness = self.get_freshness(edge_id)
        status = self.get_verification_status(edge_id)
        return {
            "verified": True,
            "freshness": freshness,
            "status": status.value,
            "observation_count": obs["observation_count"],
            "last_verified_ts": obs["last_verified_ts"]
        }

# Global singleton evidence tracker
evidence_tracker = EvidenceFreshnessTracker()
