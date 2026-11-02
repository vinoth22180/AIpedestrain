import math
import time
import pytest
import networkx as nx

from src.congestion.config import CongestionConfig
from src.congestion.manager import congestion_manager, CongestionState
from src.pada_r.router import compute_pada_route
from src.pada_r.cost_model import calculate_pada_cost
from src.graph_manager import load_or_build_graph

@pytest.fixture(autouse=True)
def clean_congestion():
    congestion_manager.reset_congestion()
    yield
    congestion_manager.reset_congestion()

def setup_deterministic_graph():
    """
    Creates a small deterministic test graph for routing tests:
    - Path 1 (Direct): START -> A -> D -> DEST (Length: 10 + 10 + 10 = 30)
    - Path 2 (Detour): START -> A -> B -> D -> DEST (Length: 10 + 7 + 7 + 10 = 34)
    - Path 3 (Stairs): START -> A -> STAIRS -> DEST (Length: 10 + 18 + 18 = 46, has stairs)
    - Path 4 (Steep):  START -> A -> SLOPE -> DEST (Length: 10 + 18 + 18 = 46, slope 15%)
    """
    G = nx.MultiDiGraph()
    G.add_node("START", x=0.0, y=0.0)
    G.add_node("A", x=10.0, y=0.0)
    G.add_node("B", x=15.0, y=6.0)
    G.add_node("D", x=20.0, y=0.0)
    G.add_node("DEST", x=30.0, y=0.0)
    G.add_node("STAIRS", x=15.0, y=-5.0)
    G.add_node("SLOPE", x=15.0, y=5.0)

    # Base walkable edges with accessible=True for wheelchair compatibility
    G.add_edge("START", "A", key="0", length_m=10.0, highway="footway", stairs=False, accessible=True)
    G.add_edge("A", "D", key="0", length_m=10.0, highway="footway", stairs=False, accessible=True, edge_id="edge:A:D:0")
    G.add_edge("D", "DEST", key="0", length_m=10.0, highway="footway", stairs=False, accessible=True)

    # Alternative detour edges (Length 11 + 11 = 22 vs 10)
    G.add_edge("A", "B", key="0", length_m=11.0, highway="footway", stairs=False, accessible=True)
    G.add_edge("B", "D", key="0", length_m=11.0, highway="footway", stairs=False, accessible=True)


    # Inaccessible paths for profile testing
    G.add_edge("A", "STAIRS", key="0", length_m=18.0, highway="steps", stairs=True, accessible=True)
    G.add_edge("STAIRS", "DEST", key="0", length_m=18.0, highway="steps", stairs=True, accessible=True)

    G.add_edge("A", "SLOPE", key="0", length_m=18.0, highway="footway", slope_percent=15.0, slope_status="measured", accessible=True)
    G.add_edge("SLOPE", "DEST", key="0", length_m=18.0, highway="footway", slope_percent=15.0, slope_status="measured", accessible=True)

    return G


# 1. A fresh YOLO observation produces the expected effective score
def test_1_fresh_yolo_observation_effective_score():
    t0 = 1000.0
    loc = "edge:A:D:0"
    job_id = congestion_manager.create_job(loc)
    congestion_manager.update_job(job_id, {
        "congestion_score": 0.80,
        "congestion_level": "SEVERE",
        "average_people": 32.0,
        "peak_people": 36,
        "timestamp": t0
    })

    eff = congestion_manager.get_effective_congestion(loc, now=t0)
    assert eff is not None
    assert eff.observed_score == 0.80
    assert eff.effective_score == 0.80
    assert eff.effective_level == "HIGH"
    assert eff.observed_level == "HIGH"
    assert eff.age_seconds == 0.0
    assert eff.status == "fresh"
    assert eff.decay_half_life_seconds == CongestionConfig.DECAY_HALF_LIFE_SECONDS

# 2. The score decays according to the configured exponential formula
def test_2_score_decays_exponentially():
    t0 = 1000.0
    loc = "edge:A:D:0"
    job_id = congestion_manager.create_job(loc)
    congestion_manager.update_job(job_id, {
        "congestion_score": 0.80,
        "timestamp": t0
    })

    elapsed = 60.0
    eff = congestion_manager.get_effective_congestion(loc, now=t0 + elapsed)
    decay_lambda = CongestionConfig.get_decay_lambda()
    expected_score = round(0.80 * math.exp(-decay_lambda * elapsed), 4)

    assert eff is not None
    assert math.isclose(eff.effective_score, expected_score, abs_tol=1e-3)
    assert eff.age_seconds == elapsed
    # Score must never exceed observed score
    assert eff.effective_score <= eff.observed_score

# 3. After one configured half-life, the score is approximately half its initial value
def test_3_half_life_reduces_score_by_half():
    t0 = 1000.0
    loc = "edge:A:D:0"
    half_life = CongestionConfig.DECAY_HALF_LIFE_SECONDS # 180.0s
    job_id = congestion_manager.create_job(loc)
    congestion_manager.update_job(job_id, {
        "congestion_score": 0.80,
        "timestamp": t0
    })

    # Exactly 1 half-life
    eff_1hl = congestion_manager.get_effective_congestion(loc, now=t0 + half_life)
    assert math.isclose(eff_1hl.effective_score, 0.40, abs_tol=1e-2)

    # Exactly 2 half-lives
    eff_2hl = congestion_manager.get_effective_congestion(loc, now=t0 + 2 * half_life)
    assert math.isclose(eff_2hl.effective_score, 0.20, abs_tol=1e-2)

# 4. A newer observation resets the decay period
def test_4_newer_observation_resets_decay_period():
    t0 = 1000.0
    loc = "edge:A:D:0"
    job_1 = congestion_manager.create_job(loc)
    congestion_manager.update_job(job_1, {"congestion_score": 0.80, "timestamp": t0})

    # Decayed state at t = 1180
    decayed = congestion_manager.get_effective_congestion(loc, now=t0 + 180.0)
    assert decayed.effective_score < 0.50

    # Newer observation at t = 1200.0 with new score 0.60
    t1 = 1200.0
    job_2 = congestion_manager.create_job(loc)
    congestion_manager.update_job(job_2, {"congestion_score": 0.60, "timestamp": t1})

    fresh = congestion_manager.get_effective_congestion(loc, now=t1)
    assert fresh.observed_score == 0.60
    assert fresh.effective_score == 0.60
    assert fresh.observed_at == t1
    assert fresh.age_seconds == 0.0
    assert fresh.status == "fresh"

    # Also test that lower score replaces rather than maxing
    t2 = 1300.0
    job_3 = congestion_manager.create_job(loc)
    congestion_manager.update_job(job_3, {"congestion_score": 0.25, "timestamp": t2})
    lower_fresh = congestion_manager.get_effective_congestion(loc, now=t2)
    assert lower_fresh.observed_score == 0.25
    assert lower_fresh.effective_score == 0.25

# 5. A failed video-processing job does not refresh congestion
def test_5_failed_job_does_not_refresh_congestion():
    t0 = 1000.0
    loc = "edge:A:D:0"
    job_1 = congestion_manager.create_job(loc)
    congestion_manager.update_job(job_1, {"congestion_score": 0.80, "timestamp": t0})

    # Failed job at t = 1100
    job_2 = congestion_manager.create_job(loc)
    congestion_manager.update_job(job_2, {
        "status": "failed",
        "error": "Corrupted frames",
        "timestamp": 1100.0
    })

    # Active state must still be anchored at t0 = 1000.0
    eff = congestion_manager.get_effective_congestion(loc, now=1100.0)
    assert eff.observed_at == t0
    assert eff.observed_score == 0.80
    assert eff.age_seconds == 100.0

# 6. An older job cannot overwrite a newer accepted observation
def test_6_stale_job_cannot_overwrite_newer_observation():
    loc = "edge:A:D:0"
    t_new = 2000.0
    t_old = 1900.0

    # New job accepted first
    job_new = congestion_manager.create_job(loc)
    congestion_manager.update_job(job_new, {"congestion_score": 0.70, "timestamp": t_new})

    # Delayed older job arrives
    job_old = congestion_manager.create_job(loc)
    congestion_manager.update_job(job_old, {"congestion_score": 0.95, "timestamp": t_old})

    # Current state must still reflect t_new
    current = congestion_manager.get_effective_congestion(loc, now=t_new)
    assert current.observed_at == t_new
    assert current.observed_score == 0.70

# 7. The effective score and level agree across the API, cost model, and frontend contract
def test_7_effective_score_and_level_consistency():
    t0 = 1000.0
    loc = "edge:A:D:0"
    job = congestion_manager.create_job(loc)
    congestion_manager.update_job(job, {"congestion_score": 0.90, "timestamp": t0})

    for check_t in [t0, t0 + 90.0, t0 + 180.0, t0 + 360.0, t0 + 900.0]:
        eff = congestion_manager.get_effective_congestion(loc, now=check_t)
        active_dict = congestion_manager.get_active_congestion(now=check_t)
        
        expected_level = CongestionConfig.get_level(eff.effective_score)
        if eff.status == "expired":
            expected_level = "LOW"

        assert eff.effective_level == expected_level
        assert active_dict[loc].effective_score == eff.effective_score
        assert active_dict[loc].congestion_level == eff.effective_level

# 8. Decayed congestion changes the actual A* edge cost
def test_8_decayed_congestion_changes_actual_edge_cost():
    G = setup_deterministic_graph()
    t0 = 1000.0
    loc = "edge:A:D:0"
    half_life = CongestionConfig.DECAY_HALF_LIFE_SECONDS

    job = congestion_manager.create_job(loc)
    congestion_manager.update_job(job, {"congestion_score": 0.80, "timestamp": t0})

    # Cost at t0 (Fresh high congestion)
    cong_t0 = congestion_manager.get_congestion_for_edge("A", "D", G, now=t0)
    edge_dict = list(G["A"]["D"].values())[0]
    _, cost_t0, bd_t0, _ = calculate_pada_cost("A", "D", edge_dict, "general", dynamic_congestion_penalty=cong_t0)

    # Cost at t0 + half_life (Decayed by 50%)
    cong_1hl = congestion_manager.get_congestion_for_edge("A", "D", G, now=t0 + half_life)
    _, cost_1hl, bd_1hl, _ = calculate_pada_cost("A", "D", edge_dict, "general", dynamic_congestion_penalty=cong_1hl)

    # Cost at t0 + 10*half_life (Negligible / Expired)
    cong_exp = congestion_manager.get_congestion_for_edge("A", "D", G, now=t0 + 10 * half_life)
    _, cost_exp, bd_exp, _ = calculate_pada_cost("A", "D", edge_dict, "general", dynamic_congestion_penalty=cong_exp)

    assert cost_t0 > cost_1hl > cost_exp
    assert bd_t0['congestion'] > bd_1hl['congestion'] > bd_exp['congestion']
    assert bd_exp['congestion'] == 0.0


# 9. An unaffected edge receives no congestion penalty
def test_9_unaffected_edge_receives_zero_congestion():
    G = setup_deterministic_graph()
    loc = "edge:A:D:0"
    job = congestion_manager.create_job(loc)
    congestion_manager.update_job(job, {"congestion_score": 0.80, "timestamp": 1000.0})

    # START -> A and D -> DEST are not congested
    assert congestion_manager.get_congestion_for_edge("START", "A", G, now=1000.0) == 0.0
    assert congestion_manager.get_congestion_for_edge("D", "DEST", G, now=1000.0) == 0.0
    assert congestion_manager.get_congestion_for_edge("A", "B", G, now=1000.0) == 0.0

# 10. The route changes when the new costs make a valid alternative preferable
def test_10_route_changes_as_congestion_decays():
    G = setup_deterministic_graph()
    t0 = 1000.0
    loc = "edge:A:D:0"
    job = congestion_manager.create_job(loc)
    # Severe congestion on the direct path A->D
    congestion_manager.update_job(job, {"congestion_score": 0.85, "timestamp": t0})

    # At t0: Direct path A->D cost is huge -> A* detours through B
    path_t0, _, _, _, stats_t0, _ = compute_pada_route(G, (0.0, 0.0), (30.0, 0.0), "general", now=t0, bypass_stability=True)
    assert path_t0 == ["START", "A", "B", "D", "DEST"], "A* must detour around fresh high congestion"

    # At t0 + 4 half-lives: Congestion on A->D has decayed to near zero -> Direct path is optimal again!
    decay_time = t0 + 4 * CongestionConfig.DECAY_HALF_LIFE_SECONDS
    path_decayed, _, _, _, stats_decayed, _ = compute_pada_route(G, (0.0, 0.0), (30.0, 0.0), "general", now=decay_time, bypass_stability=True)
    assert path_decayed == ["START", "A", "D", "DEST"], "A* must return to direct path once congestion decays"

# 11. The route remains unchanged when the current route remains optimal
def test_11_route_remains_unchanged_when_current_route_optimal():
    G = setup_deterministic_graph()
    t0 = 1000.0
    # No congestion: optimal path is direct
    path_init, _, _, _, _, _ = compute_pada_route(G, (0.0, 0.0), (30.0, 0.0), "general", now=t0)
    assert path_init == ["START", "A", "D", "DEST"]

    # Congestion added to the unused alternative path A->B
    job = congestion_manager.create_job("edge:A:B:0")
    congestion_manager.update_job(job, {"congestion_score": 0.80, "timestamp": t0})

    # Main route remains optimal and unchanged
    path_same, _, status, _, _, _ = compute_pada_route(
        G, (0.0, 0.0), (30.0, 0.0), "general",
        active_route_path=path_init,
        now=t0
    )
    assert path_same == ["START", "A", "D", "DEST"]

# 12. Accessibility hard constraints remain enforced regardless of congestion
def test_12_accessibility_hard_constraints_enforced():
    G = setup_deterministic_graph()
    t0 = 1000.0

    # Even if direct path has huge congestion, wheelchair CANNOT use stairs
    path_wheelchair, _, _, _, _, _ = compute_pada_route(G, (0.0, 0.0), (30.0, 0.0), "wheelchair", now=t0)
    assert "STAIRS" not in path_wheelchair

    # Pregnant profile CANNOT use steep slope (15% > 8%)
    path_pregnant, _, _, _, _, _ = compute_pada_route(G, (0.0, 0.0), (30.0, 0.0), "pregnant", now=t0)
    assert "SLOPE" not in path_pregnant

# 13. Map features update when effective congestion levels change
def test_13_map_features_update_with_decay():
    loc = "edge:A:D:0"
    t0 = 1000.0
    job = congestion_manager.create_job(loc)
    congestion_manager.update_job(job, {"congestion_score": 0.90, "timestamp": t0})

    # Initial HIGH
    active_t0 = congestion_manager.get_active_congestion(now=t0)[loc]
    assert active_t0.congestion_level == "HIGH"

    # Half-life 1 -> ~0.45 (MEDIUM)
    active_1hl = congestion_manager.get_active_congestion(now=t0 + CongestionConfig.DECAY_HALF_LIFE_SECONDS)[loc]
    assert active_1hl.congestion_level in ("MEDIUM", "HIGH")
    assert active_1hl.effective_score < active_t0.effective_score

    # 3 half-lives -> ~0.11 (LOW)
    active_3hl = congestion_manager.get_active_congestion(now=t0 + 3 * CongestionConfig.DECAY_HALF_LIFE_SECONDS)[loc]
    assert active_3hl.congestion_level == "LOW"

    # Beyond MAX_OBSERVATION_AGE -> EXPIRED
    active_exp = congestion_manager.get_effective_congestion(loc, now=t0 + CongestionConfig.MAX_OBSERVATION_AGE_SECONDS + 10)
    assert active_exp.status == "expired"
    assert active_exp.effective_score == 0.0

# 14. Existing YOLO processing, routing, and congestion APIs remain functional
def test_14_existing_apis_remain_functional():
    loc = "MGR"
    job_id = congestion_manager.create_job(loc)
    assert congestion_manager.get_job_status(job_id)["status"] == "processing"

    congestion_manager.update_job(job_id, {
        "average_people": 25.0,
        "peak_people": 28,
        "congestion_score": 0.62,
        "congestion_level": "HIGH",
        "unique_people": 30,
        "frames_processed": 50,
        "video_stats": {"fps": 30}
    })

    job_done = congestion_manager.get_job_status(job_id)
    assert job_done["status"] == "completed"
    assert job_done["peak_people"] == 28

    history = congestion_manager.get_history(loc)
    assert len(history) == 1
    assert history[0].peak_people == 28

    # Reset API
    congestion_manager.reset_congestion()
    assert len(congestion_manager.get_active_congestion()) == 0
    assert len(congestion_manager.get_history(loc)) == 0
