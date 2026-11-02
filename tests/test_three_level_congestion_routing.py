import pytest
import math
import time
import networkx as nx
from shapely.geometry import LineString

from src.congestion.config import CongestionConfig
from src.congestion.manager import congestion_manager
from src.pada_r.router import compute_pada_route
from src.pada_r.profiles import is_edge_allowed, PREGNANT_MAX_SLOPE, WHEELCHAIR_MAX_SLOPE

@pytest.fixture
def policy_test_graph():
    """
    Synthetic graph with Direct and Detour branches:
    - START: (0.0, 0.0)
    - DEST:  (0.0004, 0.0)
    
    Branch 1: Direct path (START -> D1 -> DEST) - 20m, flat (slope=0.0), no stairs, accessible
    Branch 2: Detour path (START -> DETOUR -> DEST) - 40m, flat (slope=0.0), no stairs, accessible
    """
    G = nx.MultiDiGraph()
    G.add_node("START", x=0.0, y=0.0)
    G.add_node("D1", x=0.0002, y=0.0)
    G.add_node("DETOUR", x=0.0002, y=0.0003)
    G.add_node("DEST", x=0.0004, y=0.0)

    # Branch 1: Direct (20m total)
    geom_d1 = LineString([(0.0, 0.0), (0.0002, 0.0)])
    geom_d2 = LineString([(0.0002, 0.0), (0.0004, 0.0)])
    G.add_edge("START", "D1", key="0", length_m=10.0, stairs=False, slope_percent=0.0, surface="asphalt", accessible=True, wheelchair="likely", geometry=geom_d1)
    G.add_edge("D1", "DEST", key="0", length_m=10.0, stairs=False, slope_percent=0.0, surface="asphalt", accessible=True, wheelchair="likely", geometry=geom_d2)

    # Branch 2: Detour (40m total)
    geom_det1 = LineString([(0.0, 0.0), (0.0002, 0.0003)])
    geom_det2 = LineString([(0.0002, 0.0003), (0.0004, 0.0)])
    G.add_edge("START", "DETOUR", key="0", length_m=20.0, stairs=False, slope_percent=0.0, surface="asphalt", accessible=True, wheelchair="likely", geometry=geom_det1)
    G.add_edge("DETOUR", "DEST", key="0", length_m=20.0, stairs=False, slope_percent=0.0, surface="asphalt", accessible=True, wheelchair="likely", geometry=geom_det2)

    return G


# =========================================================================
# 1-8: CONGESTION CLASSIFICATION TESTS
# =========================================================================

def test_01_score_0_00_is_low():
    assert CongestionConfig.get_level(0.00) == "LOW"

def test_02_score_0_2499_is_low():
    assert CongestionConfig.get_level(0.2499) == "LOW"

def test_03_score_0_25_is_medium():
    assert CongestionConfig.get_level(0.25) == "MEDIUM"

def test_04_score_0_4999_is_medium():
    assert CongestionConfig.get_level(0.4999) == "MEDIUM"

def test_05_score_0_50_is_high():
    assert CongestionConfig.get_level(0.50) == "HIGH"

def test_06_score_1_00_is_high():
    assert CongestionConfig.get_level(1.00) == "HIGH"

def test_07_legacy_severe_and_moderate_mapping():
    assert CongestionConfig.normalize_level("SEVERE") == "HIGH"
    assert CongestionConfig.normalize_level("severe") == "HIGH"
    assert CongestionConfig.normalize_level("MODERATE") == "MEDIUM"
    assert CongestionConfig.normalize_level("moderate") == "MEDIUM"
    assert CongestionConfig.normalize_level("LOW") == "LOW"
    assert CongestionConfig.normalize_level("HIGH") == "HIGH"

def test_08_invalid_missing_scores_handled_safely():
    assert CongestionConfig.get_level(None) == "LOW"
    assert CongestionConfig.get_level(float('nan')) == "LOW"
    assert CongestionConfig.get_level(float('inf')) == "LOW"
    assert CongestionConfig.get_level(-0.5) == "LOW"
    assert CongestionConfig.get_level("non_numeric") == "LOW"
    # Clamping behavior for > 1.0
    assert CongestionConfig.get_level(1.5) == "HIGH"


# =========================================================================
# 9-16: ROUTING POLICY TESTS
# =========================================================================

def test_09_general_chooses_longer_low_or_medium_over_shorter_high(policy_test_graph):
    congestion_manager.reset_congestion()
    t0 = 1000.0
    # Set HIGH congestion on Direct path (0.75)
    job = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.75, "timestamp": t0})
    
    path, _, status, exp, stats, cands = compute_pada_route(policy_test_graph, (0.0, 0.0), (0.0004, 0.0), "general", now=t0)
    assert path == ["START", "DETOUR", "DEST"]
    assert exp["avoids_congestion"] is True
    assert "Selected a longer route to avoid HIGH congestion" in exp["reason"]

def test_10_general_does_not_reroute_solely_for_medium(policy_test_graph):
    congestion_manager.reset_congestion()
    t0 = 1000.0
    # Set MEDIUM congestion on Direct path (0.35)
    job = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.35, "timestamp": t0})
    
    path, _, status, exp, stats, cands = compute_pada_route(policy_test_graph, (0.0, 0.0), (0.0004, 0.0), "general", now=t0)
    # General allows MEDIUM, so it stays on Direct (20m) rather than taking DETOUR (40m)
    assert path == ["START", "D1", "DEST"]
    assert exp["avoids_congestion"] is False

def test_11_general_retains_suitable_route_already_avoiding_high(policy_test_graph):
    congestion_manager.reset_congestion()
    t0 = 1000.0
    job = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.70, "timestamp": t0})
    
    # Active route is already DETOUR
    path, _, status, _, _, _ = compute_pada_route(
        policy_test_graph, (0.0, 0.0), (0.0004, 0.0), "general",
        active_route_path=["START", "DETOUR", "DEST"], now=t0
    )
    assert path == ["START", "DETOUR", "DEST"]

def test_12_elderly_avoids_medium_and_high_when_low_alternative_exists(policy_test_graph):
    congestion_manager.reset_congestion()
    t0 = 1000.0
    # Direct path has MEDIUM congestion (0.35)
    job = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.35, "timestamp": t0})
    
    # Elderly avoids MEDIUM and takes the longer LOW alternative (DETOUR)
    path, _, status, exp, _, _ = compute_pada_route(policy_test_graph, (0.0, 0.0), (0.0004, 0.0), "elderly", now=t0)
    assert path == ["START", "DETOUR", "DEST"]
    assert exp["avoids_congestion"] is True

def test_13_pregnant_avoids_medium_and_high_when_low_alternative_exists(policy_test_graph):
    congestion_manager.reset_congestion()
    t0 = 1000.0
    job = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.35, "timestamp": t0})
    
    path, _, status, exp, _, _ = compute_pada_route(policy_test_graph, (0.0, 0.0), (0.0004, 0.0), "pregnant", now=t0)
    assert path == ["START", "DETOUR", "DEST"]
    assert exp["avoids_congestion"] is True

def test_14_wheelchair_avoids_medium_and_high_when_low_alternative_exists(policy_test_graph):
    congestion_manager.reset_congestion()
    t0 = 1000.0
    job = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.35, "timestamp": t0})
    
    path, _, status, exp, _, _ = compute_pada_route(policy_test_graph, (0.0, 0.0), (0.0004, 0.0), "wheelchair", now=t0)
    assert path == ["START", "DETOUR", "DEST"]
    assert exp["avoids_congestion"] is True

def test_15_fallback_policy_when_no_compliant_alternative_exists(policy_test_graph):
    congestion_manager.reset_congestion()
    t0 = 1000.0
    # Direct has HIGH (0.75), DETOUR has MEDIUM (0.35)
    j1 = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(j1, {"congestion_score": 0.75, "timestamp": t0})
    j2 = congestion_manager.create_job("edge:START:DETOUR:0")
    congestion_manager.update_job(j2, {"congestion_score": 0.35, "timestamp": t0})
    
    # For Elderly, no 100% LOW alternative exists.
    # Staged fallback chooses DETOUR (MEDIUM fallback, avoiding HIGH)
    path, _, status, exp, stats, _ = compute_pada_route(policy_test_graph, (0.0, 0.0), (0.0004, 0.0), "elderly", now=t0)
    assert path == ["START", "DETOUR", "DEST"]
    assert exp["avoidance_outcome"] == "FALLBACK_MEDIUM_ALLOWED"
    assert "Notice: No fully LOW-congestion alternative was found" in exp["reason"]

def test_16_congestion_preference_cannot_override_hard_accessibility_restriction(policy_test_graph):
    G = policy_test_graph.copy()
    # Add a shorter stairs shortcut (12m total)
    G.add_node("STAIRS", x=0.0002, y=-0.0001)
    G.add_edge("START", "STAIRS", key="0", length_m=6.0, stairs=True, slope_percent=0.0, surface="concrete", accessible=False, wheelchair="no")
    G.add_edge("STAIRS", "DEST", key="0", length_m=6.0, stairs=True, slope_percent=0.0, surface="concrete", accessible=False, wheelchair="no")

    congestion_manager.reset_congestion()
    t0 = 1000.0
    # Both Direct and Detour have HIGH congestion (0.80)
    j1 = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(j1, {"congestion_score": 0.80, "timestamp": t0})
    j2 = congestion_manager.create_job("edge:START:DETOUR:0")
    congestion_manager.update_job(j2, {"congestion_score": 0.80, "timestamp": t0})
    
    # Stairs path has 0 congestion, but Wheelchair MUST NOT use stairs
    path_wc, edges_wc, status_wc, _, _, _ = compute_pada_route(G, (0.0, 0.0), (0.0004, 0.0), "wheelchair", now=t0)
    assert "STAIRS" not in path_wc
    for e in edges_wc:
        assert e.get("stairs") is not True

    # Pregnant MUST NOT use stairs
    path_pr, edges_pr, _, _, _, _ = compute_pada_route(G, (0.0, 0.0), (0.0004, 0.0), "pregnant", now=t0)
    assert "STAIRS" not in path_pr


# =========================================================================
# 17-22: ACCESSIBILITY TESTS
# =========================================================================

def test_17_elderly_does_not_receive_route_with_known_positive_slope(policy_test_graph):
    G = policy_test_graph.copy()
    # Add a shorter positive slope shortcut (12m total, slope 4%)
    G.add_node("SLOPE", x=0.0002, y=-0.0002)
    G.add_edge("START", "SLOPE", key="0", length_m=6.0, stairs=False, slope_percent=4.0, slope_status="measured", surface="asphalt", accessible=True, wheelchair="likely")
    G.add_edge("SLOPE", "DEST", key="0", length_m=6.0, stairs=False, slope_percent=4.0, slope_status="measured", surface="asphalt", accessible=True, wheelchair="likely")

    congestion_manager.reset_congestion()
    path, edges, status, _, stats, _ = compute_pada_route(G, (0.0, 0.0), (0.0004, 0.0), "elderly")
    # Elderly must choose Direct (20m, flat) over SLOPE (12m, 4% slope)
    assert "SLOPE" not in path
    assert path == ["START", "D1", "DEST"]
    for e in edges:
        slope = e.get("slope_percent")
        if slope is not None:
            assert slope <= 0.0

def test_18_pregnant_does_not_receive_stairs(policy_test_graph):
    G = policy_test_graph.copy()
    G.add_node("STAIRS", x=0.0002, y=-0.0001)
    G.add_edge("START", "STAIRS", key="0", length_m=6.0, stairs=True, slope_percent=0.0, surface="concrete", accessible=False, wheelchair="no")
    G.add_edge("STAIRS", "DEST", key="0", length_m=6.0, stairs=True, slope_percent=0.0, surface="concrete", accessible=False, wheelchair="no")

    congestion_manager.reset_congestion()
    path, edges, _, _, _, _ = compute_pada_route(G, (0.0, 0.0), (0.0004, 0.0), "pregnant")
    assert "STAIRS" not in path
    assert path == ["START", "D1", "DEST"]

def test_19_wheelchair_does_not_receive_stairs(policy_test_graph):
    G = policy_test_graph.copy()
    G.add_node("STAIRS", x=0.0002, y=-0.0001)
    G.add_edge("START", "STAIRS", key="0", length_m=6.0, stairs=True, slope_percent=0.0, surface="concrete", accessible=False, wheelchair="no")
    G.add_edge("STAIRS", "DEST", key="0", length_m=6.0, stairs=True, slope_percent=0.0, surface="concrete", accessible=False, wheelchair="no")

    congestion_manager.reset_congestion()
    path, edges, _, _, _, _ = compute_pada_route(G, (0.0, 0.0), (0.0004, 0.0), "wheelchair")
    assert "STAIRS" not in path
    assert path == ["START", "D1", "DEST"]

def test_20_wheelchair_does_not_receive_confirmed_inaccessible(policy_test_graph):
    G = policy_test_graph.copy()
    G.add_node("WC_INACC", x=0.0002, y=-0.0003)
    G.add_edge("START", "WC_INACC", key="0", length_m=6.0, stairs=False, slope_percent=0.0, surface="asphalt", accessible=False, wheelchair="no")
    G.add_edge("WC_INACC", "DEST", key="0", length_m=6.0, stairs=False, slope_percent=0.0, surface="asphalt", accessible=False, wheelchair="no")

    congestion_manager.reset_congestion()
    path, edges, _, _, _, _ = compute_pada_route(G, (0.0, 0.0), (0.0004, 0.0), "wheelchair")
    assert "WC_INACC" not in path
    assert path == ["START", "D1", "DEST"]

def test_21_unknown_slope_not_falsely_presented_as_verified_flat():
    G = nx.MultiDiGraph()
    G.add_node("U1", x=0.0, y=0.0)
    G.add_node("U2", x=0.0001, y=0.0)
    # Edge with no slope_percent attribute
    G.add_edge("U1", "U2", key="0", length_m=10.0, stairs=False, accessible=True)
    
    path, edges, status, exp, stats, _ = compute_pada_route(G, (0.0, 0.0), (0.0001, 0.0), "general")
    assert stats["accessibility_summary"]["slope_data_complete"] is False
    assert stats["accessibility_summary"]["verified_flat"] is False

def test_22_disconnected_graph_produces_clear_no_route():
    G = nx.MultiDiGraph()
    G.add_node("N1", x=0.0, y=0.0)
    G.add_node("N2", x=0.001, y=0.0)
    # No edges connecting N1 and N2
    path, edges, status, exp, stats, cands = compute_pada_route(G, (0.0, 0.0), (0.001, 0.0), "general")
    assert path is None
    assert status == "NO_ACCESSIBLE_ROUTE_FOUND"
    assert "No accessible path exists" in exp["reason"]


# =========================================================================
# 23-30: DECAY AND INTEGRATION TESTS
# =========================================================================

def test_23_fresh_yolo_immediately_affects_classification_and_routing(policy_test_graph):
    congestion_manager.reset_congestion()
    t0 = 1000.0
    job = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.85, "timestamp": t0})
    
    # Fresh observation -> HIGH -> General reroutes to DETOUR
    path, _, _, exp, _, _ = compute_pada_route(policy_test_graph, (0.0, 0.0), (0.0004, 0.0), "general", now=t0)
    assert path == ["START", "DETOUR", "DEST"]

def test_24_decayed_high_becomes_medium_then_low():
    congestion_manager.reset_congestion()
    t0 = 1000.0
    loc = "test_decay_edge"
    job = congestion_manager.create_job(loc)
    congestion_manager.update_job(job, {"congestion_score": 0.80, "timestamp": t0})
    
    # At t0: 0.80 -> HIGH
    c0 = congestion_manager.get_effective_congestion(loc, now=t0)
    assert c0.effective_level == "HIGH"
    
    # At 1.5 half-lives: 0.80 * exp(-ln(2)*1.5) = 0.80 * (0.5^1.5) ≈ 0.2828 -> MEDIUM
    t_1_5 = t0 + 1.5 * CongestionConfig.DECAY_HALF_LIFE_SECONDS
    c_med = congestion_manager.get_effective_congestion(loc, now=t_1_5)
    assert c_med.effective_level == "MEDIUM"
    assert 0.25 <= c_med.effective_score < 0.50
    
    # At 3 half-lives: 0.80 * (0.5^3) = 0.10 -> LOW
    t_3 = t0 + 3.0 * CongestionConfig.DECAY_HALF_LIFE_SECONDS
    c_low = congestion_manager.get_effective_congestion(loc, now=t_3)
    assert c_low.effective_level == "LOW"
    assert c_low.effective_score < 0.25

def test_25_general_routing_changes_when_high_decays_to_medium(policy_test_graph):
    congestion_manager.reset_congestion()
    t0 = 1000.0
    loc = "edge:START:D1:0"
    job = congestion_manager.create_job(loc)
    congestion_manager.update_job(job, {"congestion_score": 0.80, "timestamp": t0})
    
    # At t0 (HIGH): General avoids Direct, takes DETOUR
    p_t0, _, _, _, _, _ = compute_pada_route(policy_test_graph, (0.0, 0.0), (0.0004, 0.0), "general", now=t0)
    assert p_t0 == ["START", "DETOUR", "DEST"]
    
    # At 1.5 half-lives (MEDIUM): General allows MEDIUM, returns to Direct
    t_med = t0 + 1.5 * CongestionConfig.DECAY_HALF_LIFE_SECONDS
    p_med, _, _, _, _, _ = compute_pada_route(policy_test_graph, (0.0, 0.0), (0.0004, 0.0), "general", now=t_med)
    assert p_med == ["START", "D1", "DEST"]

def test_26_elderly_continues_avoiding_medium_but_accepts_low(policy_test_graph):
    congestion_manager.reset_congestion()
    t0 = 1000.0
    loc = "edge:START:D1:0"
    job = congestion_manager.create_job(loc)
    congestion_manager.update_job(job, {"congestion_score": 0.80, "timestamp": t0})
    
    # At 1.5 half-lives (MEDIUM): Elderly STILL avoids Direct (MEDIUM) and takes DETOUR
    t_med = t0 + 1.5 * CongestionConfig.DECAY_HALF_LIFE_SECONDS
    p_med, _, _, exp_med, _, _ = compute_pada_route(policy_test_graph, (0.0, 0.0), (0.0004, 0.0), "elderly", now=t_med)
    assert p_med == ["START", "DETOUR", "DEST"]
    
    # At 3 half-lives (LOW): Elderly accepts Direct (LOW) and takes Direct
    t_low = t0 + 3.0 * CongestionConfig.DECAY_HALF_LIFE_SECONDS
    p_low, _, _, _, _, _ = compute_pada_route(policy_test_graph, (0.0, 0.0), (0.0004, 0.0), "elderly", now=t_low)
    assert p_low == ["START", "D1", "DEST"]

def test_27_newer_valid_observation_resets_decay_clock():
    congestion_manager.reset_congestion()
    t0 = 1000.0
    loc = "test_reset_loc"
    j1 = congestion_manager.create_job(loc)
    congestion_manager.update_job(j1, {"congestion_score": 0.80, "timestamp": t0})
    
    # Advance time by 2 half-lives -> score has decayed to ~0.20
    t1 = t0 + 2.0 * CongestionConfig.DECAY_HALF_LIFE_SECONDS
    c_decayed = congestion_manager.get_effective_congestion(loc, now=t1)
    assert c_decayed.effective_score < 0.25
    
    # Newer observation arrives at t1 with score 0.70
    j2 = congestion_manager.create_job(loc)
    congestion_manager.update_job(j2, {"congestion_score": 0.70, "timestamp": t1})
    
    # State is reset to fresh starting at t1
    c_new = congestion_manager.get_effective_congestion(loc, now=t1)
    assert c_new.effective_score == 0.70
    assert c_new.effective_level == "HIGH"
    assert c_new.status == "fresh"

def test_28_failed_or_stale_job_cannot_refresh_or_overwrite():
    congestion_manager.reset_congestion()
    t_fresh = 2000.0
    loc = "test_stale_loc"
    j_fresh = congestion_manager.create_job(loc)
    congestion_manager.update_job(j_fresh, {"congestion_score": 0.60, "timestamp": t_fresh})
    
    # Stale job with earlier timestamp t=1500.0 arrives
    j_stale = congestion_manager.create_job(loc)
    congestion_manager.update_job(j_stale, {"congestion_score": 0.95, "timestamp": 1500.0})
    
    # Should not overwrite newer observation
    state = congestion_manager.get_effective_congestion(loc, now=t_fresh)
    assert state.observed_score == 0.60
    assert state.observed_at == t_fresh
    
    # Failed job should not refresh timestamp or state
    j_failed = congestion_manager.create_job(loc)
    congestion_manager.update_job(j_failed, {"status": "failed", "timestamp": 3000.0})
    state_after_fail = congestion_manager.get_effective_congestion(loc, now=t_fresh)
    assert state_after_fail.observed_at == t_fresh

def test_29_active_congestion_map_uses_effective_three_level_values():
    congestion_manager.reset_congestion()
    t0 = 1000.0
    loc = "edge:START:D1:0"
    job = congestion_manager.create_job(loc)
    congestion_manager.update_job(job, {"congestion_score": 0.75, "timestamp": t0})
    
    active = congestion_manager.get_active_congestion(now=t0)
    assert loc in active
    st = active[loc]
    assert st.effective_level in ("LOW", "MEDIUM", "HIGH")
    assert st.effective_level == "HIGH"

def test_30_existing_routing_and_geometry_remain_intact(policy_test_graph):
    congestion_manager.reset_congestion()
    path, edges, status, exp, stats, candidates = compute_pada_route(
        policy_test_graph, (0.0, 0.0), (0.0004, 0.0), "general"
    )
    assert len(candidates) >= 1
    rec = candidates[0]
    assert rec["category"] == "Recommended"
    assert rec["distance"] > 0
    assert rec["total_cost"] > 0
    assert rec["walking_time"] > 0
    assert rec["congestion_level"] in ("LOW", "MEDIUM", "HIGH")
    assert rec["geojson"]["type"] == "Feature"
    assert rec["geojson"]["geometry"]["type"] == "LineString"
    assert len(rec["geojson"]["geometry"]["coordinates"]) >= 2
