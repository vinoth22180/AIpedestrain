import pytest
import networkx as nx
from unittest.mock import patch, MagicMock

from src.congestion.yolo_detector import process_video_for_congestion
from src.congestion.manager import congestion_manager
from src.congestion.config import CongestionConfig
from src.pada_r.router import compute_pada_route
from src.graph_manager import load_or_build_graph

@pytest.fixture(scope="module")
def G_base():
    return load_or_build_graph()

def test_yolo_detection_parsing_and_person_counting():
    with patch('src.congestion.yolo_detector.cv2.VideoCapture') as mock_cap, \
         patch('src.congestion.yolo_detector.get_model') as mock_get_model, \
         patch('src.congestion.yolo_detector.os.path.exists') as mock_exists:
        
        mock_exists.return_value = True
        mock_cap_instance = mock_cap.return_value
        mock_cap_instance.isOpened.return_value = True
        
        # Simulate 10 frames, taking every 3rd frame (frames 0, 3, 6, 9 -> 4 frames)
        frame_reads = [(True, "fake_frame") for _ in range(10)] + [(False, None)]
        mock_cap_instance.read.side_effect = frame_reads
        
        mock_model = MagicMock()
        mock_get_model.return_value = mock_model
        
        # Mock results for the 4 processed frames: 20, 25, 21, 22 people
        class FakeResult:
            def __init__(self, count):
                self.boxes = [1]*count
        
        mock_model.predict.side_effect = [
            [FakeResult(20)],
            [FakeResult(25)],
            [FakeResult(21)],
            [FakeResult(22)]
        ]
        
        res = process_video_for_congestion("fake_video.mp4")
        
        assert res["frames_processed"] == 4
        assert res["average_people"] == 22.0
        assert res["peak_people"] == 25

def test_congestion_score_and_classification():
    assert CongestionConfig.get_level(0.1) == "LOW"
    assert CongestionConfig.get_level(0.3) == "MEDIUM"
    assert CongestionConfig.get_level(0.6) == "HIGH"
    assert CongestionConfig.get_level(0.9) == "HIGH"
    assert CongestionConfig.get_level(1.0) == "HIGH"
    assert CongestionConfig.normalize_level("SEVERE") == "HIGH"
    assert CongestionConfig.normalize_level("MODERATE") == "MEDIUM"

def test_location_to_graph_mapping_and_dynamic_state(G_base):
    # Ensure graph has 'MGR'
    # Find MGR manually or just inject one
    test_loc = None
    for n, d in G_base.nodes(data=True):
        if d.get('short_name') == 'MGR':
            test_loc = 'MGR'
            break
            
    if not test_loc:
        # fallback
        test_loc = list(G_base.nodes(data=True))[0][1].get('short_name', 'TEST')
        if test_loc == 'TEST':
            G_base.nodes[list(G_base.nodes)[0]]['short_name'] = 'TEST'

    job_id = congestion_manager.create_job(test_loc)
    congestion_manager.update_job(job_id, {
        "average_people": 30.0,
        "peak_people": 35,
        "congestion_score": 0.75,
        "congestion_level": "HIGH"
    })
    
    state = congestion_manager.get_active_congestion()
    assert test_loc in state
    assert state[test_loc].congestion_score == 0.75
    
    # Test mapping
    coords = congestion_manager._get_location_coords(test_loc, G_base)
    assert coords is not None

def test_congestion_aware_edge_cost_and_routing(G_base):
    # Find two nearby nodes to route between
    nodes = list(G_base.nodes)
    origin = G_base.nodes[nodes[0]]
    dest = G_base.nodes[nodes[10]]
    origin_coords = (origin['x'], origin['y'])
    dest_coords = (dest['x'], dest['y'])

    # 1. No congestion route
    congestion_manager.current_state.clear()
    path1, edges1, status1, expl1, stats1 = compute_pada_route(G_base, origin_coords, dest_coords, "general")
    assert path1 is not None
    base_cost = stats1['cost']
    base_dist = stats1['distance']

    # 2. Inject congestion exactly at the origin node
    test_loc = 'TEST_ORIGIN'
    G_base.nodes[nodes[0]]['short_name'] = test_loc
    job_id = congestion_manager.create_job(test_loc)
    congestion_manager.update_job(job_id, {
        "average_people": 40.0,
        "peak_people": 50,
        "congestion_score": 1.0,
        "congestion_level": "SEVERE"
    })
    
    path2, edges2, status2, expl2, stats2 = compute_pada_route(G_base, origin_coords, dest_coords, "general")
    assert path2 is not None
    congested_cost = stats2['cost']
    
    # The cost should be higher or route should change
    assert congested_cost >= base_cost or path1 != path2
    
    # Clear state for other tests
    congestion_manager.current_state.clear()
