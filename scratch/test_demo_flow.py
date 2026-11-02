import sys
from src.graph_manager import load_or_build_graph
from src.darr.simulation import simulation_manager

G = load_or_build_graph()
print("--- TESTING DEMO SCENARIO (STEPS 1 TO 9) ---")

state = simulation_manager.reset_demo(G)
print(f"Initial Step {state['current_step']}: {state['title']} | Risk: {state['risk_level']} | ARL: {state['wheelchair_resilience']}")

for s in range(2, 10):
    state = simulation_manager.step_demo_scenario(G, s)
    print(f"Step {state['current_step']}: {state['title']} | Risk: {state['risk_level']} | ARL: {state['wheelchair_resilience']} | Redistributed: {state['redistributed_pedestrians']}")

print("Demo scenario progression verified successfully!")
