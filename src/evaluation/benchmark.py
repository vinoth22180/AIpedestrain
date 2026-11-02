import time
from src.graph_manager import load_or_build_graph
from src.pada_r.router import compute_pada_route

def run_benchmark():
    print("Loading graph for benchmark...")
    G = load_or_build_graph()
    
    # Common origin/destination in CBD
    origin = (144.965, -37.813)
    destination = (144.955, -37.820)
    
    print("Benchmarking General Profile Route Calculation...")
    start_time = time.time()
    for _ in range(10):
        compute_pada_route(G, origin, destination, "general", None, None)
    end_time = time.time()
    
    print(f"Average Route Time (General): {((end_time - start_time) / 10) * 1000:.2f} ms")

if __name__ == "__main__":
    run_benchmark()
