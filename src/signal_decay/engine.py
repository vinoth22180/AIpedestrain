import math
import uuid
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from src.config.loader import WEIGHTS_CONFIG

@dataclass
class DecayEvent:
    event_id: str
    edge: Tuple[int, int]
    initial_penalty: float
    current_penalty: float
    lambda_rate: float
    created_time: float
    last_update_time: float
    event_type: str
    is_active: bool = True

class SignalDecayEngine:
    def __init__(self):
        self.default_lambda = WEIGHTS_CONFIG['signal_decay'].get('lambda_rate', 0.005)
        self.epsilon = WEIGHTS_CONFIG['signal_decay'].get('epsilon', 1.0)
        self.events: Dict[str, DecayEvent] = {}
        self.last_update_time = 0.0 # simulation clock source of truth

    def update_time(self, current_time: float):
        """
        Advances the simulation time and decays existing penalties incrementally.
        D_new = D_old * exp(-lambda * delta_t)
        """
        delta_t = current_time - self.last_update_time
        if delta_t <= 0:
            return
            
        for event_id, event in list(self.events.items()):
            if not event.is_active:
                continue
                
            # Incremental decay based on delta from event's last update
            event_delta_t = current_time - event.last_update_time
            if event_delta_t > 0:
                decay_factor = math.exp(-event.lambda_rate * event_delta_t)
                
                # For logging
                prev_penalty = event.current_penalty
                
                event.current_penalty *= decay_factor
                event.last_update_time = current_time
                
                if event.current_penalty < self.epsilon:
                    event.is_active = False
                    event.current_penalty = 0.0
                    print(f"[DECAY] Event expired\\nEdge: {event.edge}")
                else:
                    print(f"[DECAY] Event updated\\nElapsed: {event_delta_t:.1f}\\nPrevious penalty: {prev_penalty:.2f}\\nCurrent penalty: {event.current_penalty:.2f}")
            
        self.last_update_time = current_time

    def add_penalty(self, u, v, penalty_value: float, event_type: str = "HIGH", lambda_rate: Optional[float] = None) -> str:
        """
        I_e(t): Injects an instantaneous penalty to an edge as an independent event.
        """
        event_id = str(uuid.uuid4())
        eff_lambda = lambda_rate if lambda_rate is not None else self.default_lambda
        
        event = DecayEvent(
            event_id=event_id,
            edge=(u, v),
            initial_penalty=penalty_value,
            current_penalty=penalty_value,
            lambda_rate=eff_lambda,
            created_time=self.last_update_time,
            last_update_time=self.last_update_time,
            event_type=event_type,
            is_active=True
        )
        self.events[event_id] = event
        
        print(f"[DECAY] Event created\\nEdge: {event.edge}\\nD0: {penalty_value}\\nLambda: {eff_lambda}\\nTime: {self.last_update_time}")
        
        # Graph is undirected, so add to reverse as well
        rev_event_id = str(uuid.uuid4())
        rev_event = DecayEvent(
            event_id=rev_event_id,
            edge=(v, u),
            initial_penalty=penalty_value,
            current_penalty=penalty_value,
            lambda_rate=eff_lambda,
            created_time=self.last_update_time,
            last_update_time=self.last_update_time,
            event_type=event_type,
            is_active=True
        )
        self.events[rev_event_id] = rev_event
        
        return event_id

    def get_penalty(self, u, v) -> float:
        """
        Returns total D_e(t) for the given edge by summing active events.
        """
        total = 0.0
        for event in self.events.values():
            if event.is_active and event.edge == (u, v):
                total += event.current_penalty
        return total

    def predict_penalty_at(self, u, v, target_time: float) -> float:
        """
        Estimates the predicted decayed penalty D_e(target_time) at a future simulation time.
        Does not mutate active event states.
        """
        if target_time <= self.last_update_time:
            return self.get_penalty(u, v)
            
        total = 0.0
        for event in self.events.values():
            if event.is_active and event.edge == (u, v):
                delta_t = target_time - event.last_update_time
                if delta_t > 0:
                    pred = event.current_penalty * math.exp(-event.lambda_rate * delta_t)
                    if pred >= self.epsilon:
                        total += pred
                else:
                    total += event.current_penalty
        return total

    def get_active_events(self) -> List[dict]:
        """
        Exports state for the frontend visualization.
        """
        return [
            {
                "event_id": e.event_id,
                "edge": e.edge,
                "initial_penalty": e.initial_penalty,
                "current_penalty": e.current_penalty,
                "lambda_rate": e.lambda_rate,
                "created_time": e.created_time,
                "last_update_time": e.last_update_time,
                "elapsed_time": self.last_update_time - e.created_time,
                "event_type": e.event_type
            }
            for e in self.events.values() if e.is_active
        ]

    def reset(self):
        self.events = {}
        self.last_update_time = 0.0

decay_engine = SignalDecayEngine()
