import pytest
import time
import math
import networkx as nx
from shapely.geometry import LineString
from fastapi.testclient import TestClient

from src.congestion.manager import congestion_manager, CongestionState
from src.congestion.config import CongestionConfig
from src.pada_r.router import compute_pada_route
from src.api import app, G_base


# ---------------------------------------------------------------------------
# Fixtures and Synthetic Graph Builders
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_congestion():
    """Ensure clean congestion manager state for every test."""
    congestion_manager.reset_congestion()
    yield
    congestion_manager.reset_congestion()


def build_two_path_graph():
    """
    Creates a synthetic graph with two paths between START and DEST:
    - Path A (Short): START -> A -> DEST (Length: 10 + 10 = 20m)
    - Path B (Long):  START -> B -> DEST (Length: 20 + 20 = 40m)
    """
    G = nx.MultiDiGraph()
    G.add_node("START", x=0.0, y=0.0)
    G.add_node("A", x=0.0001, y=0.0)
    G.add_node("B", x=0.0001, y=0.0002)
    G.add_node("DEST", x=0.0002, y=0.0)

    # Path A
    G.add_edge("START", "A", key="0", length_m=10.0, highway="footway", stairs=False, slope_percent=0.0, accessible=True, edge_id="edge:START:A:0", geometry=LineString([(0, 0), (0.0001, 0)]))
    G.add_edge("A", "DEST", key="0", length_m=10.0, highway="footway", stairs=False, slope_percent=0.0, accessible=True, edge_id="edge:A:DEST:0", geometry=LineString([(0.0001, 0), (0.0002, 0)]))

    # Path B
    G.add_edge("START", "B", key="0", length_m=20.0, highway="footway", stairs=False, slope_percent=0.0, accessible=True, edge_id="edge:START:B:0", geometry=LineString([(0, 0), (0.0001, 0.0002)]))
    G.add_edge("B", "DEST", key="0", length_m=20.0, highway="footway", stairs=False, slope_percent=0.0, accessible=True, edge_id="edge:B:DEST:0", geometry=LineString([(0.0001, 0.0002), (0.0002, 0)]))

    return G


def build_multi_od_synthetic_graph():
    """
    Grid/diamond graph with multiple OD pairs:
    Nodes: O1, O2, M1, M2, D1, D2
    """
    G = nx.MultiDiGraph()
    G.add_node("O1", x=0.0, y=0.0)
    G.add_node("O2", x=0.0, y=0.001)
    G.add_node("M1", x=0.001, y=0.0)
    G.add_node("M2", x=0.001, y=0.001)
    G.add_node("D1", x=0.002, y=0.0)
    G.add_node("D2", x=0.002, y=0.001)

    # Walkway edges
    def add_e(u, v, length, eid):
        G.add_edge(u, v, key="0", length_m=length, highway="footway", stairs=False, slope_percent=0.0, accessible=True, edge_id=eid)

    add_e("O1", "M1", 10.0, "edge:O1:M1:0")
    add_e("M1", "D1", 10.0, "edge:M1:D1:0")

    add_e("O1", "M2", 25.0, "edge:O1:M2:0")
    add_e("M2", "D1", 25.0, "edge:M2:D1:0")

    add_e("O2", "M2", 10.0, "edge:O2:M2:0")
    add_e("M2", "D2", 10.0, "edge:M2:D2:0")

    add_e("O2", "M1", 25.0, "edge:O2:M1:0")
    add_e("M1", "D2", 25.0, "edge:M1:D2:0")

    return G


# ---------------------------------------------------------------------------
# Test A — Direct route becomes HIGH
# ---------------------------------------------------------------------------
def test_A_direct_route_becomes_high():
    """Verify General profile selects Route B (longer LOW) when Route A is HIGH."""
    G = build_two_path_graph()
    t0 = 1000.0

    # Inject HIGH congestion on Path A edge
    job = congestion_manager.create_job("edge:START:A:0")
    congestion_manager.update_job(job, {"congestion_score": 0.85, "timestamp": t0})

    path, edges, status, exp, stats, cands = compute_pada_route(G, (0.0, 0.0), (0.0002, 0.0), "general", now=t0)

    assert path == ["START", "B", "DEST"]
    assert stats['distance'] == 40.0
    assert exp['avoids_congestion'] is True
    assert exp['avoidance_outcome'] == "STRICT_AVOIDED"
    assert "Selected a longer route to avoid HIGH congestion" in exp['reason']


# ---------------------------------------------------------------------------
# Test B — All origin/destination pairs on synthetic graph
# ---------------------------------------------------------------------------
def test_B_multi_od_pairs_avoid_high():
    """For every tested OD pair where a valid HIGH-free path exists, General avoids HIGH edges."""
    G = build_multi_od_synthetic_graph()
    t0 = 1000.0

    # Congest M1 entirely
    job1 = congestion_manager.create_job("edge:O1:M1:0")
    congestion_manager.update_job(job1, {"congestion_score": 0.90, "timestamp": t0})

    # Test pair 1: O1 -> D1 (Baseline through M1 is 20m, Detour through M2 is 50m)
    p1, _, _, exp1, stats1, _ = compute_pada_route(G, (0.0, 0.0), (0.002, 0.0), "general", now=t0)
    assert p1 == ["O1", "M2", "D1"]
    assert "M1" not in p1
    assert exp1['avoids_congestion'] is True

    # Test pair 2: O2 -> D2 (Natural route is O2 -> M2 -> D2, completely unaffected by M1)
    p2, _, _, exp2, stats2, _ = compute_pada_route(G, (0.0, 0.001), (0.002, 0.001), "general", now=t0)
    assert p2 == ["O2", "M2", "D2"]
    assert stats2['distance'] == 20.0
    assert exp2['avoids_congestion'] is False


# ---------------------------------------------------------------------------
# Test C — MEDIUM behavior: General accepts, Vulnerable avoids
# ---------------------------------------------------------------------------
def test_C_medium_congestion_behavior():
    """General stays on shortest path with MEDIUM; vulnerable profiles take LOW alternative."""
    G = build_two_path_graph()
    t0 = 1000.0

    # Medium congestion (score = 0.35) on short Path A
    job = congestion_manager.create_job("edge:START:A:0")
    congestion_manager.update_job(job, {"congestion_score": 0.35, "timestamp": t0})

    # 1. General accepts MEDIUM on shortest route
    p_gen, _, _, exp_gen, stats_gen, _ = compute_pada_route(G, (0.0, 0.0), (0.0002, 0.0), "general", now=t0)
    assert p_gen == ["START", "A", "DEST"]
    assert stats_gen['distance'] == 20.0
    assert exp_gen['avoids_congestion'] is False
    assert "Active pedestrian congestion (MEDIUM)" in exp_gen['reason']

    # 2. Elderly avoids MEDIUM and takes LOW detour B
    p_eld, _, _, exp_eld, stats_eld, _ = compute_pada_route(G, (0.0, 0.0), (0.0002, 0.0), "elderly", now=t0)
    assert p_eld == ["START", "B", "DEST"]
    assert stats_eld['distance'] == 40.0
    assert exp_eld['avoids_congestion'] is True
    assert "Selected a longer route to avoid MEDIUM congestion" in exp_eld['reason']

    # 3. Pregnant avoids MEDIUM and takes LOW detour B
    p_preg, _, _, exp_preg, stats_preg, _ = compute_pada_route(G, (0.0, 0.0), (0.0002, 0.0), "pregnant", now=t0)
    assert p_preg == ["START", "B", "DEST"]
    assert stats_preg['distance'] == 40.0
    assert exp_preg['avoids_congestion'] is True

    # 4. Wheelchair avoids MEDIUM and takes LOW detour B
    p_wc, _, _, exp_wc, stats_wc, _ = compute_pada_route(G, (0.0, 0.0), (0.0002, 0.0), "wheelchair", now=t0)
    assert p_wc == ["START", "B", "DEST"]
    assert stats_wc['distance'] == 40.0
    assert exp_wc['avoids_congestion'] is True


# ---------------------------------------------------------------------------
# Test D — HIGH observation mapping and invalid location rejection
# ---------------------------------------------------------------------------
def test_D_observation_mapping_and_validation():
    """Verify E001926 resolves on campus graph and invalid location returns HTTP 400."""
    client = TestClient(app)

    # 1. Valid location: E001926 exists on campus graph
    assert congestion_manager.is_valid_location("E001926") is True
    assert congestion_manager.is_valid_location("MGR") is True

    # 2. Invalid location: does not exist
    assert congestion_manager.is_valid_location("TOTALLY_BOGUS_EDGE_99999") is False

    # 3. Upload video endpoint rejects unresolvable location with HTTP 400
    fake_video = ("test.mp4", b"fake video bytes", "video/mp4")
    res = client.post(
        "/api/congestion/video",
        data={"location": "TOTALLY_BOGUS_EDGE_99999"},
        files={"file": fake_video}
    )
    assert res.status_code == 400
    assert "cannot be resolved" in res.json().get("detail", "")


# ---------------------------------------------------------------------------
# Test E — MultiGraph parallel edge-key integrity
# ---------------------------------------------------------------------------
def test_E_multigraph_parallel_edge_keys():
    """Router correctly differentiates parallel edges between same nodes by key and cost."""
    G = nx.MultiDiGraph()
    G.add_node("U", x=0.0, y=0.0)
    G.add_node("V", x=0.0001, y=0.0)

    # Key 0: Flat asphalt walkway (Length: 10m)
    geom_0 = LineString([(0, 0), (0.0001, 0)])
    G.add_edge("U", "V", key="k_flat", length_m=10.0, highway="footway", stairs=False, slope_percent=0.0, surface="asphalt", accessible=True, edge_id="E_FLAT", geometry=geom_0)

    # Key 1: Steep slope walkway (Length: 10m, slope 12%)
    geom_1 = LineString([(0, 0), (0.0001, 0)])
    G.add_edge("U", "V", key="k_steep", length_m=10.0, highway="footway", stairs=False, slope_percent=12.0, slope_status="measured", surface="asphalt", accessible=True, edge_id="E_STEEP", geometry=geom_1)

    # Pregnant profile strictly avoids slope > 5% -> must choose k_flat
    path, path_edges, status, exp, stats, _ = compute_pada_route(G, (0.0, 0.0), (0.0001, 0.0), "pregnant")
    assert path == ["U", "V"]
    assert len(path_edges) == 1
    assert path_edges[0]['key'] == "k_flat"
    assert path_edges[0]['edge_id'] == "E_FLAT"


# ---------------------------------------------------------------------------
# Test F — Live congestion update triggers route change
# ---------------------------------------------------------------------------
def test_F_live_congestion_update_triggers_reroute():
    """A subsequent route request after observation update selects the alternative path."""
    G = build_two_path_graph()
    t0 = 1000.0

    # Step 1: Initial route request with no congestion -> Path A (20m)
    p1, _, _, exp1, stats1, _ = compute_pada_route(G, (0.0, 0.0), (0.0002, 0.0), "general", now=t0)
    assert p1 == ["START", "A", "DEST"]
    assert stats1['distance'] == 20.0

    # Step 2: Observation becomes HIGH on Path A
    job = congestion_manager.create_job("edge:START:A:0")
    congestion_manager.update_job(job, {"congestion_score": 0.80, "timestamp": t0})

    # Step 3: Subsequent route request with same endpoints -> Path B (40m)
    p2, _, _, exp2, stats2, _ = compute_pada_route(G, (0.0, 0.0), (0.0002, 0.0), "general", now=t0)
    assert p2 == ["START", "B", "DEST"]
    assert stats2['distance'] == 40.0
    assert exp2['avoids_congestion'] is True


# ---------------------------------------------------------------------------
# Test G — No compliant alternative available
# ---------------------------------------------------------------------------
def test_G_fallback_when_all_paths_high():
    """When all feasible paths have HIGH congestion, router returns best feasible and discloses it."""
    G = build_two_path_graph()
    t0 = 1000.0

    # Congest BOTH Path A and Path B as HIGH
    job_a = congestion_manager.create_job("edge:START:A:0")
    congestion_manager.update_job(job_a, {"congestion_score": 0.85, "timestamp": t0})
    job_b = congestion_manager.create_job("edge:START:B:0")
    congestion_manager.update_job(job_b, {"congestion_score": 0.70, "timestamp": t0})

    path, _, status, exp, stats, _ = compute_pada_route(G, (0.0, 0.0), (0.0002, 0.0), "general", now=t0)

    # General falls back to lowest-cost feasible path (Path A, 20m vs 40m)
    assert path == ["START", "A", "DEST"]
    assert exp['avoids_congestion'] is False
    assert exp['avoidance_outcome'] == "FALLBACK_ALL_CONGESTED"
    assert "No fully congestion-avoiding route was found" in exp['reason']


# ---------------------------------------------------------------------------
# Test H — Accessibility precedence over congestion
# ---------------------------------------------------------------------------
def test_H_accessibility_precedence_over_congestion():
    """Hard constraints (wheelchair stairs, pregnant slopes) are NEVER bypassed for congestion."""
    G = nx.MultiDiGraph()
    G.add_node("START", x=0.0, y=0.0)
    G.add_node("STAIRS", x=0.0001, y=0.0)
    G.add_node("RAMP", x=0.0001, y=0.0002)
    G.add_node("DEST", x=0.0002, y=0.0)

    # Path 1: Steps (stairs=True) - completely LOW congestion
    G.add_edge("START", "STAIRS", key="0", length_m=10.0, highway="steps", stairs=True, accessible=True, edge_id="E_STAIRS1")
    G.add_edge("STAIRS", "DEST", key="0", length_m=10.0, highway="steps", stairs=True, accessible=True, edge_id="E_STAIRS2")

    # Path 2: Ramp/walkway (accessible=True, stairs=False) - has HIGH congestion
    G.add_edge("START", "RAMP", key="0", length_m=20.0, highway="footway", ramp=True, stairs=False, accessible=True, edge_id="E_RAMP1")
    G.add_edge("RAMP", "DEST", key="0", length_m=20.0, highway="footway", ramp=True, stairs=False, accessible=True, edge_id="E_RAMP2")

    t0 = 1000.0
    job = congestion_manager.create_job("E_RAMP1")
    congestion_manager.update_job(job, {"congestion_score": 0.80, "timestamp": t0})

    # Wheelchair profile: MUST NEVER take STAIRS, even if ramp is congested!
    path_wc, _, status_wc, exp_wc, stats_wc, _ = compute_pada_route(G, (0.0, 0.0), (0.0002, 0.0), "wheelchair", now=t0)
    assert path_wc == ["START", "RAMP", "DEST"]
    assert "STAIRS" not in path_wc
    assert stats_wc['accessibility']['stairs_avoided'] is True


# ---------------------------------------------------------------------------
# Test I — Route metadata and diagnostics consistency
# ---------------------------------------------------------------------------
def test_I_diagnostics_and_metadata_consistency():
    """API /api/route returns structured diagnostics describing the exact edge sequence."""
    client = TestClient(app)
    t0 = 1000.0

    # Inject HIGH observation on Jimmy Carter Road walkway near SJT
    job = congestion_manager.create_job("E001926")
    congestion_manager.update_job(job, {"congestion_score": 1.0, "timestamp": t0, "average_people": 40.0, "peak_people": 40})

    with TestClient(app) as client:
        # Request MGR -> Gandhi Block
        res = client.post("/api/route", json={
            "origin": [79.15583638463455, 12.969035851408112],
            "destination": [79.16799249061337, 12.972225506107774],
            "profile": "general",
            "now": t0 + 140.0
        })
        assert res.status_code == 200
        data = res.json()

        assert "diagnostics" in data
        diag = data["diagnostics"]
        assert diag["rerouted"] is True
        assert diag["compliant_alternative_exists"] is True
        assert "E000084" in diag["baseline_high_edges"]
        assert "E000084" not in diag["selected_edge_ids"]
        assert data["route_explanation"]["avoids_congestion"] is True


# ---------------------------------------------------------------------------
# Test J — Full VIT campus graph MGR -> Gandhi Block regression test
# ---------------------------------------------------------------------------
def test_J_campus_graph_mgr_gandhi_block_avoidance():
    """Real campus network test: E001926 HIGH reroutes from SJT corridor (1550m) to Lake bypass (1779m)."""
    if G_base is None:
        from src.graph_manager import load_or_build_graph
        G = load_or_build_graph()
    else:
        G = G_base

    origin = (79.15583638463455, 12.969035851408112)
    dest = (79.16799249061337, 12.972225506107774)
    t0 = 1000000.0

    # 1. Baseline
    p_base, edges_base, _, _, stats_base, _ = compute_pada_route(G, origin, dest, "general", now=t0)
    base_ids = [e.get('edge_id') for e in edges_base]
    assert stats_base['distance'] == pytest.approx(1550.80, rel=1e-3)
    assert 'E000084' in base_ids
    assert 'E000083' in base_ids

    # 2. Add HIGH observation on E001926 (decayed to ~0.58 at t0+140s)
    job = congestion_manager.create_job("E001926")
    congestion_manager.update_job(job, {"congestion_score": 1.0, "timestamp": t0, "average_people": 40.0, "peak_people": 40})

    # 3. Request route again with General
    p_reroute, edges_reroute, _, exp_reroute, stats_reroute, _ = compute_pada_route(G, origin, dest, "general", now=t0 + 140.0)
    reroute_ids = [e.get('edge_id') for e in edges_reroute]

    # Verify corridor is completely avoided
    assert 'E000084' not in reroute_ids
    assert 'E000083' not in reroute_ids
    assert 'E001926' not in reroute_ids
    assert exp_reroute['avoids_congestion'] is True
    assert stats_reroute['distance'] > stats_base['distance']
    assert stats_reroute['distance'] == pytest.approx(1779.41, rel=1e-3)
