import pytest
import math
import time
import networkx as nx
from shapely.geometry import LineString
from starlette.testclient import TestClient

from src.congestion.config import CongestionConfig
from src.congestion.manager import congestion_manager
from src.pada_r.router import compute_pada_route
from src.pada_r.cost_model import calculate_pada_cost
from src.pada_r.profiles import PREGNANT_MAX_SLOPE, WHEELCHAIR_MAX_SLOPE
from src.api import app

@pytest.fixture
def regression_graph():
    """
    Deterministic synthetic graph with:
    - Route A (Direct): START -> A1 -> DEST (20m total length)
    - Route B (Detour): START -> B1 -> DEST (25m total length, only 5m longer)
    Both are accessible, flat, and have no stairs.
    """
    G = nx.MultiDiGraph()
    G.add_node("START", x=0.0, y=0.0)
    G.add_node("A1", x=0.0001, y=0.0)
    G.add_node("B1", x=0.0001, y=0.00015)
    G.add_node("DEST", x=0.0002, y=0.0)

    # Route A (Direct, 20m)
    geom_a1 = LineString([(0.0, 0.0), (0.0001, 0.0)])
    geom_a2 = LineString([(0.0001, 0.0), (0.0002, 0.0)])
    G.add_edge("START", "A1", key="0", length_m=10.0, stairs=False, slope_percent=0.0, surface="asphalt", accessible=True, wheelchair="likely", geometry=geom_a1)
    G.add_edge("A1", "DEST", key="0", length_m=10.0, stairs=False, slope_percent=0.0, surface="asphalt", accessible=True, wheelchair="likely", geometry=geom_a2)

    # Route B (Detour, 25m)
    geom_b1 = LineString([(0.0, 0.0), (0.0001, 0.00015)])
    geom_b2 = LineString([(0.0001, 0.00015), (0.0002, 0.0)])
    G.add_edge("START", "B1", key="0", length_m=12.5, stairs=False, slope_percent=0.0, surface="asphalt", accessible=True, wheelchair="likely", geometry=geom_b1)
    G.add_edge("B1", "DEST", key="0", length_m=12.5, stairs=False, slope_percent=0.0, surface="asphalt", accessible=True, wheelchair="likely", geometry=geom_b2)

    return G


# -----------------------------------------------------------------------------
# 1. General stays on a suitable route under MEDIUM congestion
# -----------------------------------------------------------------------------
def test_1_general_stays_on_shortest_under_medium_congestion(regression_graph):
    """
    Proves General accepts MEDIUM congestion and does NOT divert onto a longer detour
    (Route B is 25m, Route A is 20m).
    """
    congestion_manager.reset_congestion()
    t0 = 1000.0
    # Inject MEDIUM congestion (score 0.35) on Route A
    job = congestion_manager.create_job("edge:START:A1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.35, "timestamp": t0})

    path, path_edges, status, exp, stats, cands = compute_pada_route(
        regression_graph, (0.0, 0.0), (0.0002, 0.0), "general", now=t0
    )

    # General remains on Route A (Direct 20m)
    assert path == ["START", "A1", "DEST"]
    assert exp["avoids_congestion"] is False
    assert stats["distance"] == 20.0
    congestion_manager.reset_congestion()


# -----------------------------------------------------------------------------
# 2. General avoids HIGH congestion when a valid alternative exists
# -----------------------------------------------------------------------------
def test_2_general_avoids_high_congestion(regression_graph):
    """
    Proves General avoids HIGH congestion (score 0.75) and selects the 25m detour (Route B).
    """
    congestion_manager.reset_congestion()
    t0 = 1000.0
    # Inject HIGH congestion (score 0.75) on Route A
    job = congestion_manager.create_job("edge:START:A1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.75, "timestamp": t0})

    path, path_edges, status, exp, stats, cands = compute_pada_route(
        regression_graph, (0.0, 0.0), (0.0002, 0.0), "general", now=t0
    )

    # General reroutes onto Route B (Detour 25m)
    assert path == ["START", "B1", "DEST"]
    assert exp["avoids_congestion"] is True
    assert "Selected a longer route to avoid HIGH congestion" in exp["reason"]
    assert stats["distance"] == 25.0
    congestion_manager.reset_congestion()


# -----------------------------------------------------------------------------
# 3. Vulnerable profiles avoid MEDIUM/HIGH when a valid LOW alternative exists
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("profile", ["elderly", "pregnant", "wheelchair"])
def test_3_vulnerable_profiles_avoid_medium_congestion(regression_graph, profile):
    """
    Proves Elderly, Pregnant, and Wheelchair avoid MEDIUM congestion when a valid
    LOW-congestion alternative (Route B) exists.
    """
    congestion_manager.reset_congestion()
    t0 = 1000.0
    # Inject MEDIUM congestion (score 0.35) on Route A
    job = congestion_manager.create_job("edge:START:A1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.35, "timestamp": t0})

    path, path_edges, status, exp, stats, cands = compute_pada_route(
        regression_graph, (0.0, 0.0), (0.0002, 0.0), profile, now=t0
    )

    # All vulnerable profiles divert to Route B (Detour 25m)
    assert path == ["START", "B1", "DEST"]
    assert exp["avoids_congestion"] is True
    assert stats["distance"] == 25.0
    congestion_manager.reset_congestion()


@pytest.mark.parametrize("profile", ["elderly", "pregnant", "wheelchair"])
def test_3b_vulnerable_profiles_avoid_high_congestion(regression_graph, profile):
    """
    Proves Elderly, Pregnant, and Wheelchair avoid HIGH congestion when a valid
    LOW-congestion alternative (Route B) exists.
    """
    congestion_manager.reset_congestion()
    t0 = 1000.0
    # Inject HIGH congestion (score 0.75) on Route A
    job = congestion_manager.create_job("edge:START:A1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.75, "timestamp": t0})

    path, path_edges, status, exp, stats, cands = compute_pada_route(
        regression_graph, (0.0, 0.0), (0.0002, 0.0), profile, now=t0
    )

    assert path == ["START", "B1", "DEST"]
    assert exp["avoids_congestion"] is True
    assert stats["distance"] == 25.0
    congestion_manager.reset_congestion()


# -----------------------------------------------------------------------------
# 4. Congestion metadata is computed from selected route, not campus-wide state
# -----------------------------------------------------------------------------
def test_4_route_congestion_metadata_isolated_from_unrelated_campus_congestion():
    """
    Proves that severe/high congestion on an unrelated campus edge does NOT bleed into
    the congestion level, score, or explanation of a completely clean route.
    """
    with TestClient(app) as client:
        congestion_manager.reset_congestion()
        t0 = 1000.0

        # Inject HIGH congestion on a distant edge (e.g. edge:1:2:0)
        job = congestion_manager.create_job("edge:9999999:8888888:0")
        congestion_manager.update_job(job, {"congestion_score": 0.95, "timestamp": t0})

        # Request a route between MGR and SMV on the real campus network
        # MGR: [79.15788, 12.96918], SMV: [79.15881, 12.96924]
        resp = client.post("/api/route", json={
            "origin": [79.15788, 12.96918],
            "destination": [79.15881, 12.96924],
            "profile": "general",
            "now": t0
        })

        assert resp.status_code == 200
        data = resp.json()

        # The route itself is completely clean (unaffected by distant edge)
        assert data["congestion_score"] == 0.0
        assert data["congestion_level"] == "LOW"
        assert data["accessibility_summary"]["max_congestion_score"] == 0.0
        assert data["accessibility_summary"]["max_congestion_level"] == "LOW"
        assert data["route_explanation"]["avoids_congestion"] is False
        assert "Selected a longer route to avoid" not in data["decision_summary"]
        
        # Campus-wide congestion manager does still have the active job
        active_congs = congestion_manager.get_active_congestion()
        assert len(active_congs) >= 1

        congestion_manager.reset_congestion()


# -----------------------------------------------------------------------------
# 5. UI displays MEDIUM correctly
# -----------------------------------------------------------------------------
def test_5_congestion_levels_and_ui_medium_definition():
    """
    Verifies that MEDIUM congestion is defined strictly in [0.25, 0.50)
    and that UI styling references match amber/warning.
    """
    assert CongestionConfig.get_level(0.25) == "MEDIUM"
    assert CongestionConfig.get_level(0.35) == "MEDIUM"
    assert CongestionConfig.get_level(0.4999) == "MEDIUM"
    assert CongestionConfig.get_level(0.50) == "HIGH"
    assert CongestionConfig.get_level(0.2499) == "LOW"

    # Verify Sidebar.jsx code contains the MEDIUM styling with amber background
    with open("frontend/src/components/Sidebar.jsx", "r", encoding="utf-8") as f:
        sidebar_code = f.read()

    # Amber hex color #fef3c7 and text #92400e must be present for MEDIUM
    assert "#fef3c7" in sidebar_code
    assert "#92400e" in sidebar_code
    assert "MED CONG" in sidebar_code


# -----------------------------------------------------------------------------
# 6. Refreshing frontend does not automatically erase congestion state
# -----------------------------------------------------------------------------
def test_6_refresh_frontend_does_not_reset_congestion():
    """
    Verifies that:
    1. App.jsx has no automatic reset call on mount.
    2. Simulated browser requests preserve active congestion across consecutive requests.
    """
    with open("frontend/src/App.jsx", "r", encoding="utf-8") as f:
        app_code = f.read()

    # App.jsx must not have a useEffect calling /api/congestion/reset on mount
    assert "/api/congestion/reset" not in app_code

    # Verify backend persistence across multiple client sessions
    with TestClient(app) as client:
        congestion_manager.reset_congestion()
        t0 = 2000.0

        job_id = congestion_manager.create_job("edge:A:B:0")
        congestion_manager.update_job(job_id, {"congestion_score": 0.65, "timestamp": t0})

        # First request
        resp1 = client.get("/api/congestion/active")
        assert resp1.status_code == 200
        assert len(resp1.json()["active_congestions"]) == 1

        # Simulate second page load / refresh 10 seconds later
        resp2 = client.get("/api/congestion/active")
        assert resp2.status_code == 200
        assert len(resp2.json()["active_congestions"]) == 1
        assert resp2.json()["active_congestions"][0]["location"] == "edge:A:B:0"

        congestion_manager.reset_congestion()


# -----------------------------------------------------------------------------
# 7. Existing decay and accessibility behavior still works
# -----------------------------------------------------------------------------
def test_7_accessibility_hard_constraints_and_exponential_decay():
    """
    Proves:
    1. Wheelchair rejects stairs unconditionally.
    2. Pregnant rejects slopes above PREGNANT_MAX_SLOPE (5%).
    3. Congestion decays exponentially according to half-life.
    """
    # 1. Wheelchair rejects stairs
    stairs_edge = {"stairs": True, "length_m": 10.0, "slope_percent": 0.0}
    status, cost, _, reasons = calculate_pada_cost("U", "V", stairs_edge, "wheelchair")
    assert status == "INACCESSIBLE"
    assert math.isinf(cost)

    # 2. Pregnant rejects steep slope (> 5%)
    steep_edge = {"stairs": False, "length_m": 10.0, "slope_percent": 6.5}
    status_pr, cost_pr, _, _ = calculate_pada_cost("U", "V", steep_edge, "pregnant")
    assert status_pr == "INACCESSIBLE"
    assert math.isinf(cost_pr)

    # 3. Congestion decays exponentially
    congestion_manager.reset_congestion()
    t0 = 3000.0
    hl = CongestionConfig.DECAY_HALF_LIFE_SECONDS
    loc = "edge:TEST:1:0"
    job = congestion_manager.create_job(loc)
    congestion_manager.update_job(job, {"congestion_score": 0.80, "timestamp": t0})

    eff_0 = congestion_manager.get_effective_congestion(loc, now=t0)
    assert eff_0.effective_score == 0.80

    # At 1 half-life, effective score must be halved (0.40)
    eff_1hl = congestion_manager.get_effective_congestion(loc, now=t0 + hl)
    assert abs(eff_1hl.effective_score - 0.40) < 0.001
    assert eff_1hl.effective_level == "MEDIUM"

    # At 2 half-lives, effective score must be halved again (0.20)
    eff_2hl = congestion_manager.get_effective_congestion(loc, now=t0 + 2 * hl)
    assert abs(eff_2hl.effective_score - 0.20) < 0.001
    assert eff_2hl.effective_level == "LOW"

    # Explicit reset works
    congestion_manager.reset_congestion()
    assert len(congestion_manager.get_active_congestion()) == 0
