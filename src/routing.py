import networkx as nx
import math

def get_nearest_node(G, point):
    """Finds the nearest node in graph G to the given (lng, lat) point."""
    lng, lat = point
    best_node = None
    min_dist = float('inf')
    
    for n, data in G.nodes(data=True):
        if 'x' in data and 'y' in data:
            dist = math.hypot(data['x'] - lng, data['y'] - lat)
            if dist < min_dist:
                min_dist = dist
                best_node = n
                
    return best_node

def get_nearest_edge(G, point):
    """Finds the nearest edge in graph G to the given (lng, lat) point."""
    lng, lat = point
    best_edge = None
    best_geom = None
    min_dist = float('inf')
    
    for u, v, data in G.edges(data=True):
        if 'geometry' in data:
            coords = data['geometry'].coords
            # Just test endpoints and midpoints for simplicity
            for c_lng, c_lat in coords:
                dist = math.hypot(c_lng - lng, c_lat - lat)
                if dist < min_dist:
                    min_dist = dist
                    best_edge = (u, v)
                    
                    # Convert coords to format expected by frontend (list of [lon, lat])
                    best_geom = [[c[0], c[1]] for c in coords]
        else:
            # Check nodes
            u_data = G.nodes[u]
            v_data = G.nodes[v]
            
            u_coords = [u_data.get('x', 0), u_data.get('y', 0)]
            v_coords = [v_data.get('x', 0), v_data.get('y', 0)]
            
            if 'x' in u_data and 'y' in u_data:
                dist_u = math.hypot(u_coords[0] - lng, u_coords[1] - lat)
                if dist_u < min_dist:
                    min_dist = dist_u
                    best_edge = (u, v)
                    best_geom = [u_coords, v_coords]
                    
            if 'x' in v_data and 'y' in v_data:
                dist_v = math.hypot(v_coords[0] - lng, v_coords[1] - lat)
                if dist_v < min_dist:
                    min_dist = dist_v
                    best_edge = (u, v)
                    best_geom = [u_coords, v_coords]
                    
    if best_edge:
        return best_edge[0], best_edge[1], best_geom, min_dist
    return None, None, None, None
