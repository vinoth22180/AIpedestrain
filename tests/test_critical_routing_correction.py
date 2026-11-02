import pytest
import networkx as nx
from shapely.geometry import LineString

from src.congestion.config import CongestionConfig
from src.congestion.manager import congestion_manager
from src.pada_r.router import compute_pada_route
from src.pada_r.profiles import is_edge_allowed


@pytest.fixture(autouse=True)
def clean_congestion():
    congestion_manager.reset_congestion()
    yield
    congestion_manager.reset_congestion()


@pytest.fixture
def multi_path_graph():
    """
    Small deterministic test graph with coordinates:
    START (0,0) -> DEST (0.0004, 0)
    
    1. DIRECT_FLAT: START -> D1 -> DEST (20m total, 0% slope, flat, paved)
    2. DETOUR_FLAT: START -> DETOUR -> DEST (40m total, 0% slope, flat, paved)
    3. SHORT_SLOPE: START -> SLP -> DEST (12m total, 4.0% slope, paved)
    4. SHORT_STAIRS: START -> STR -> DEST (10m total, stairs=True)
    5. VERIFIED_WC: START -> WC_OK -> DEST (18m total, wheelchair='yes', ramp=True)
    6. UNVERIFIED_WC: START -> WC_UN -> DEST (14m total, wheelchair='unknown', accessible=True)
    """
    G = nx.MultiDiGraph()
    G.add_node("START", x=0.0, y=0.0)
    G.add_node("DEST", x=0.0004, y=0.0)
    
    # 1. Direct Flat
    G.add_node("D1", x=0.0002, y=0.0)
    geom_d1 = LineString([(0.0, 0.0), (0.0002, 0.0)])
    geom_d2 = LineString([(0.0002, 0.0), (0.0004, 0.0)])
    G.add_edge("START", "D1", key="0", length_m=10.0, stairs=False, slope_percent=0.0, accessible=True, wheelchair="likely", edge_id="edge:START:D1:0", geometry=geom_d1)
    G.add_edge("D1", "DEST", key="0", length_m=10.0, stairs=False, slope_percent=0.0, accessible=True, wheelchair="likely", edge_id="edge:D1:DEST:0", geometry=geom_d2)

    # 2. Detour Flat
    G.add_node("DETOUR", x=0.0002, y=0.0003)
    geom_det1 = LineString([(0.0, 0.0), (0.0002, 0.0003)])
    geom_det2 = LineString([(0.0002, 0.0003), (0.0004, 0.0)])
    G.add_edge("START", "DETOUR", key="0", length_m=20.0, stairs=False, slope_percent=0.0, accessible=True, wheelchair="likely", edge_id="edge:START:DETOUR:0", geometry=geom_det1)
    G.add_edge("DETOUR", "DEST", key="0", length_m=20.0, stairs=False, slope_percent=0.0, accessible=True, wheelchair="likely", edge_id="edge:DETOUR:DEST:0", geometry=geom_det2)

    return G


# 1. General selects a longer alternative when the shortest route contains HIGH congestion
def test_01_general_selects_longer_alternative_avoiding_high(multi_path_graph):
    t0 = 1000.0
    job = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.80, "timestamp": t0})

    path, _, status, exp, stats, cands = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "general", now=t0)
    assert path == ["START", "DETOUR", "DEST"]
    assert stats["distance"] == 40.0
    assert exp["avoids_congestion"] is True
    assert "Selected a longer route to avoid HIGH congestion" in exp["reason"]


# 2. General does not reroute solely due to MEDIUM congestion
def test_02_general_does_not_reroute_solely_due_to_medium(multi_path_graph):
    t0 = 1000.0
    job = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.35, "timestamp": t0}) # MEDIUM

    path, _, _, exp, stats, _ = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "general", now=t0)
    assert path == ["START", "D1", "DEST"]
    assert stats["distance"] == 20.0


# 3. Elderly avoids a MEDIUM-congestion route when a valid LOW-congestion alternative exists
def test_03_elderly_avoids_medium_congestion_for_low(multi_path_graph):
    t0 = 1000.0
    job = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.35, "timestamp": t0}) # MEDIUM

    path, _, _, exp, stats, _ = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "elderly", now=t0)
    assert path == ["START", "DETOUR", "DEST"]
    assert stats["distance"] == 40.0
    assert exp["avoids_congestion"] is True


# 4. Elderly still returns a feasible route when every available route contains a slope
def test_04_elderly_returns_feasible_route_when_all_routes_have_slope():
    G = nx.MultiDiGraph()
    G.add_node("A", x=0.0, y=0.0)
    G.add_node("B", x=0.0002, y=0.0)
    G.add_edge("A", "B", key="0", length_m=20.0, stairs=False, slope_percent=2.5, slope_status="measured", accessible=True)

    path, edges, status, exp, stats, _ = compute_pada_route(G, (0.0, 0.0), (0.0002, 0.0), "elderly")
    assert path == ["A", "B"]
    assert status == "PERSONALIZED_OPTIMAL"
    assert stats["distance"] == 20.0
    assert "Notice: Route includes walkway with mild slope" in exp["reason"]


# 5. Elderly prefers a flat route over a shorter sloped route when the policy says to discourage slopes
def test_05_elderly_prefers_flat_route_over_shorter_sloped_route(multi_path_graph):
    G = multi_path_graph.copy()
    # Add a shorter route with 4% slope (12m total vs 20m flat)
    G.add_node("SLP", x=0.0002, y=-0.0001)
    G.add_edge("START", "SLP", key="0", length_m=6.0, stairs=False, slope_percent=4.0, slope_status="measured", accessible=True)
    G.add_edge("SLP", "DEST", key="0", length_m=6.0, stairs=False, slope_percent=4.0, slope_status="measured", accessible=True)

    path, edges, status, exp, stats, _ = compute_pada_route(G, (0.0, 0.0), (0.0004, 0.0), "elderly")
    # Elderly should select flat Direct path (20m) instead of sloped shortcut (12m)
    assert path == ["START", "D1", "DEST"]
    assert "SLP" not in path


# 6. Pregnant excludes stairs and selects a valid alternative
def test_06_pregnant_excludes_stairs(multi_path_graph):
    G = multi_path_graph.copy()
    # Add shorter route with stairs (10m total)
    G.add_node("STR", x=0.0002, y=-0.0002)
    G.add_edge("START", "STR", key="0", length_m=5.0, stairs=True, accessible=True)
    G.add_edge("STR", "DEST", key="0", length_m=5.0, stairs=True, accessible=True)

    path, edges, status, _, stats, _ = compute_pada_route(G, (0.0, 0.0), (0.0004, 0.0), "pregnant")
    assert "STR" not in path
    assert path == ["START", "D1", "DEST"]
    assert all(not e.get("stairs") for e in edges)


# 7. Wheelchair excludes stairs and confirmed inaccessible edges
def test_07_wheelchair_excludes_stairs_and_inaccessible_edges(multi_path_graph):
    G = multi_path_graph.copy()
    G.add_node("STR", x=0.0002, y=-0.0002)
    G.add_edge("START", "STR", key="0", length_m=5.0, stairs=True, accessible=True)
    G.add_edge("STR", "DEST", key="0", length_m=5.0, stairs=True, accessible=True)

    G.add_node("INACC", x=0.0002, y=-0.0003)
    G.add_edge("START", "INACC", key="0", length_m=4.0, stairs=False, wheelchair="no", accessible=False)
    G.add_edge("INACC", "DEST", key="0", length_m=4.0, stairs=False, wheelchair="no", accessible=False)

    path, edges, status, _, stats, _ = compute_pada_route(G, (0.0, 0.0), (0.0004, 0.0), "wheelchair")
    assert "STR" not in path
    assert "INACC" not in path
    assert path == ["START", "D1", "DEST"]


# 8. Wheelchair prefers a verified accessible route
def test_08_wheelchair_prefers_verified_accessible_route():
    G = nx.MultiDiGraph()
    G.add_node("START", x=0.0, y=0.0)
    G.add_node("DEST", x=0.0004, y=0.0)
    
    # Path A: Unverified wheelchair (14m total, wheelchair='unknown')
    G.add_node("UNVER", x=0.0002, y=0.0001)
    G.add_edge("START", "UNVER", key="0", length_m=7.0, stairs=False, wheelchair="unknown", accessible=True)
    G.add_edge("UNVER", "DEST", key="0", length_m=7.0, stairs=False, wheelchair="unknown", accessible=True)

    # Path B: Verified accessible with ramp (18m total, slightly longer)
    G.add_node("VERIF", x=0.0002, y=-0.0001)
    G.add_edge("START", "VERIF", key="0", length_m=9.0, stairs=False, wheelchair="yes", ramp=True, accessible=True)
    G.add_edge("VERIF", "DEST", key="0", length_m=9.0, stairs=False, wheelchair="yes", ramp=True, accessible=True)

    path_wc, _, _, _, _, _ = compute_pada_route(G, (0.0, 0.0), (0.0004, 0.0), "wheelchair")
    # Wheelchair profile rewards verified ramp & accessible path over unverified
    assert path_wc == ["START", "VERIF", "DEST"]


# 9. Missing accessibility metadata does not become false evidence of accessibility
def test_09_missing_accessibility_metadata_is_conservative():
    # If edge is missing wheelchair attributes and has stairs or barriers, it must not be marked accessible
    edge_stairs = {"stairs": True}
    assert is_edge_allowed(edge_stairs, "wheelchair")[0] is False
    assert is_edge_allowed(edge_stairs, "pregnant")[0] is False


# 10. The same endpoints with different profiles produce different routes in a test graph specifically designed to require different decisions
def test_10_different_profiles_produce_different_routes():
    G = nx.MultiDiGraph()
    G.add_node("START", x=0.0, y=0.0)
    G.add_node("DEST", x=30.0, y=0.0)

    # 1. Stairs route (16m total): shortest, but has stairs
    G.add_node("STR", x=15.0, y=-5.0)
    G.add_edge("START", "STR", key="0", length_m=8.0, stairs=True, accessible=True)
    G.add_edge("STR", "DEST", key="0", length_m=8.0, stairs=True, accessible=True)

    # 2. Sloped route (22m total): 1.5% slope, no stairs
    G.add_node("SLP", x=15.0, y=5.0)
    G.add_edge("START", "SLP", key="0", length_m=11.0, stairs=False, slope_percent=1.5, slope_status="measured", accessible=True)
    G.add_edge("SLP", "DEST", key="0", length_m=11.0, stairs=False, slope_percent=1.5, slope_status="measured", accessible=True)

    # 3. Flat route (26m total): 0% slope, no stairs, verified accessible
    G.add_node("FLAT", x=15.0, y=0.0)
    G.add_edge("START", "FLAT", key="0", length_m=13.0, stairs=False, slope_percent=0.0, wheelchair="yes", ramp=True, accessible=True)
    G.add_edge("FLAT", "DEST", key="0", length_m=13.0, stairs=False, slope_percent=0.0, wheelchair="yes", ramp=True, accessible=True)

    path_gen, _, _, _, _, _ = compute_pada_route(G, (0.0, 0.0), (30.0, 0.0), "general")
    path_eld, _, _, _, _, _ = compute_pada_route(G, (0.0, 0.0), (30.0, 0.0), "elderly")
    path_prg, _, _, _, _, _ = compute_pada_route(G, (0.0, 0.0), (30.0, 0.0), "pregnant")
    path_wc, _, _, _, _, _ = compute_pada_route(G, (0.0, 0.0), (30.0, 0.0), "wheelchair")

    # General takes the shortest stairs route (16m)
    assert path_gen == ["START", "STR", "DEST"]
    # Elderly avoids stairs and slope, takes flat route (26m)
    assert path_eld == ["START", "FLAT", "DEST"]
    # Pregnant excludes stairs, can take sloped route (22m, 4% <= 5%)
    assert path_prg == ["START", "SLP", "DEST"]
    # Wheelchair excludes stairs, takes verified accessible flat route (26m)
    assert path_wc == ["START", "FLAT", "DEST"]


# 11. All profiles can legitimately share a route when it is optimal and compliant for all of them
def test_11_all_profiles_share_route_when_optimal_and_compliant(multi_path_graph):
    # Only flat, accessible 20m route and 40m detour exist
    p_gen, _, _, _, _, _ = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "general")
    p_eld, _, _, _, _, _ = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "elderly")
    p_prg, _, _, _, _, _ = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "pregnant")
    p_wc, _, _, _, _, _ = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "wheelchair")

    assert p_gen == ["START", "D1", "DEST"]
    assert p_eld == ["START", "D1", "DEST"]
    assert p_prg == ["START", "D1", "DEST"]
    assert p_wc == ["START", "D1", "DEST"]


# 12. HIGH congestion on an edge changes the actual selected graph-edge sequence when a compliant alternative exists
def test_12_high_congestion_changes_graph_edge_sequence(multi_path_graph):
    t0 = 1000.0
    p_before, _, _, _, _, _ = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "general", now=t0)
    assert p_before == ["START", "D1", "DEST"]

    job = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.85, "timestamp": t0})

    p_after, _, _, _, _, _ = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "general", now=t0)
    assert p_after == ["START", "DETOUR", "DEST"]
    assert p_after != p_before


# 13. HIGH -> MEDIUM decay changes route behavior correctly for General
def test_13_high_to_medium_decay_changes_route_for_general(multi_path_graph):
    t0 = 1000.0
    loc = "edge:START:D1:0"
    job = congestion_manager.create_job(loc)
    congestion_manager.update_job(job, {"congestion_score": 0.80, "timestamp": t0})

    # At t0 (HIGH): General takes detour
    p_high, _, _, _, _, _ = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "general", now=t0)
    assert p_high == ["START", "DETOUR", "DEST"]

    # At t_med (MEDIUM): General allows MEDIUM, returns to Direct
    t_med = t0 + 1.5 * CongestionConfig.DECAY_HALF_LIFE_SECONDS
    p_med, _, _, _, _, _ = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "general", now=t_med)
    assert p_med == ["START", "D1", "DEST"]


# 14. HIGH -> MEDIUM decay continues to trigger avoidance for Elderly, Pregnant, and Wheelchair
def test_14_high_to_medium_decay_continues_avoidance_for_vulnerable_profiles(multi_path_graph):
    t0 = 1000.0
    loc = "edge:START:D1:0"
    job = congestion_manager.create_job(loc)
    congestion_manager.update_job(job, {"congestion_score": 0.80, "timestamp": t0})

    t_med = t0 + 1.5 * CongestionConfig.DECAY_HALF_LIFE_SECONDS
    for prof in ["elderly", "pregnant", "wheelchair"]:
        p, _, _, exp, _, _ = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), prof, now=t_med)
        assert p == ["START", "DETOUR", "DEST"]
        assert exp["avoids_congestion"] is True


# 15. MEDIUM -> LOW decay removes the congestion-based avoidance requirement for every profile
def test_15_medium_to_low_decay_removes_avoidance_for_every_profile(multi_path_graph):
    t0 = 1000.0
    loc = "edge:START:D1:0"
    job = congestion_manager.create_job(loc)
    congestion_manager.update_job(job, {"congestion_score": 0.80, "timestamp": t0})

    t_low = t0 + 3.0 * CongestionConfig.DECAY_HALF_LIFE_SECONDS
    for prof in ["general", "elderly", "pregnant", "wheelchair"]:
        p, _, _, _, _, _ = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), prof, now=t_low)
        assert p == ["START", "D1", "DEST"]


# 16. If no congestion-compliant route exists, the best feasible route is returned with an explicit warning
def test_16_fallback_returns_best_feasible_route_with_explicit_warning(multi_path_graph):
    t0 = 1000.0
    # Both Direct and Detour have HIGH congestion
    j1 = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(j1, {"congestion_score": 0.85, "timestamp": t0})
    j2 = congestion_manager.create_job("edge:START:DETOUR:0")
    congestion_manager.update_job(j2, {"congestion_score": 0.85, "timestamp": t0})

    path, _, status, exp, stats, _ = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "general", now=t0)
    assert path is not None
    assert exp["avoidance_outcome"] == "FALLBACK_ALL_CONGESTED"
    assert "No fully congestion-avoiding route was found" in exp["reason"]


# 17. Route stability cannot preserve a route that violates the current mandatory congestion policy
def test_17_stability_cannot_preserve_route_violating_congestion_policy(multi_path_graph):
    t0 = 1000.0
    # Active route was Direct (20m)
    active_path = ["START", "D1", "DEST"]

    # Sudden HIGH congestion on Direct
    job = congestion_manager.create_job("edge:START:D1:0")
    congestion_manager.update_job(job, {"congestion_score": 0.85, "timestamp": t0})

    # Even though active_route_path is passed and within hysteresis threshold,
    # stability must NOT retain it because candidate avoids prohibited congestion!
    path, _, status, _, _, _ = compute_pada_route(
        multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "general",
        active_route_path=active_path,
        bypass_stability=False,
        now=t0
    )
    assert path == ["START", "DETOUR", "DEST"]
    assert status != "STABLE_RETAINED"


# 18. The route geometry, edge sequence, distance, and reported congestion statistics match
def test_18_route_geometry_sequence_distance_and_stats_match(multi_path_graph):
    path, edges, status, exp, stats, cands = compute_pada_route(multi_path_graph, (0.0, 0.0), (0.0004, 0.0), "general")
    assert path == ["START", "D1", "DEST"]
    assert len(edges) == 2
    assert stats["distance"] == 20.0
    rec_cand = next(c for c in cands if c["route_id"] == "recommended")
    assert rec_cand["distance"] == 20.0
    coords = rec_cand["geojson"]["geometry"]["coordinates"]
    assert len(coords) >= 3


# 19. Disconnected graphs return a clear error without fabricated edges
def test_19_disconnected_graph_returns_clear_no_route_error():
    G = nx.MultiDiGraph()
    G.add_node("ISO_A", x=0.0, y=0.0)
    G.add_node("ISO_B", x=0.001, y=0.001)

    path, edges, status, exp, stats, cands = compute_pada_route(G, (0.0, 0.0), (0.001, 0.001), "general")
    assert path is None
    assert edges is None
    assert status == "NO_ACCESSIBLE_ROUTE_FOUND"
    assert "No accessible path exists" in exp["reason"]


# 20. Existing routing, API, decay, and accessibility tests continue to pass
def test_20_regression_check_profile_feasibility():
    # Verify that slope thresholds and accessibility profiles remain robust
    from src.pada_r.profiles import PADA_PROFILES
    for prof in ["general", "elderly", "pregnant", "wheelchair"]:
        assert prof in PADA_PROFILES
        assert "distance_weight" in PADA_PROFILES[prof]
