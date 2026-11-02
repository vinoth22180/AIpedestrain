import pytest
import math
from src.signal_decay.engine import SignalDecayEngine, DecayEvent

def test_decay_initialization():
    engine = SignalDecayEngine()
    engine.default_lambda = 0.5
    engine.last_update_time = 0.0

    # D0 = 100
    engine.add_penalty("A", "B", 100.0, event_type="HIGH", lambda_rate=0.5)
    
    # At t=0, penalty should be D0
    assert engine.get_penalty("A", "B") == 100.0

def test_exponential_decay():
    engine = SignalDecayEngine()
    engine.default_lambda = 0.5
    engine.last_update_time = 0.0

    engine.add_penalty("A", "B", 100.0, event_type="HIGH", lambda_rate=0.5)
    
    # Advance time by 1 unit: Δt = 1
    engine.update_time(1.0)
    
    # Expected: 100 * exp(-0.5 * 1) = 60.653
    current_penalty = engine.get_penalty("A", "B")
    expected = 100.0 * math.exp(-0.5 * 1.0)
    
    assert math.isclose(current_penalty, expected, rel_tol=1e-3)

def test_multiple_events_aggregation():
    engine = SignalDecayEngine()
    engine.last_update_time = 0.0
    
    # Event 1 at t=0
    engine.add_penalty("A", "B", 50.0, lambda_rate=0.1)
    
    engine.update_time(5.0)
    
    # Event 2 at t=5
    engine.add_penalty("A", "B", 50.0, lambda_rate=0.1)
    
    # Expected penalty at t=5:
    # Event 1: 50 * exp(-0.1 * 5) = 50 * 0.6065 = 30.325
    # Event 2: 50
    # Total = 80.325
    
    total = engine.get_penalty("A", "B")
    expected = (50.0 * math.exp(-0.1 * 5.0)) + 50.0
    
    assert math.isclose(total, expected, rel_tol=1e-3)

def test_event_expiration():
    engine = SignalDecayEngine()
    engine.epsilon = 1.0
    engine.last_update_time = 0.0
    
    engine.add_penalty("A", "B", 10.0, lambda_rate=1.0)
    
    # Advance time by 10 units
    engine.update_time(10.0)
    
    # Expected: 10 * exp(-10) = 0.00045, which is < epsilon (1.0)
    # So event should be expired and penalty should be 0.
    assert engine.get_penalty("A", "B") == 0.0
