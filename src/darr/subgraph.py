import networkx as nx
from typing import Dict, Any, Tuple, Optional, Set
from src.darr.config import get_profile_config, ProfileConfig

class AccessibleSubgraphManager:
    """
    Dynamically derives the currently feasible pedestrian subgraph G_profile(t)
    for each user profile by applying physical and dynamic barriers.
    """

    @staticmethod
    def is_edge_accessible(edge_data: Dict[str, Any], profile_cfg: ProfileConfig, u: Any = None, v: Any = None) -> Tuple[bool, str]:
        """
        Evaluates whether an edge meets the physical and dynamic constraints of the profile.
        Returns (is_accessible, failure_reason).
        """
        # 1. Stairs constraint
        has_stairs = edge_data.get('stairs', False)
        highway = str(edge_data.get('highway', ''))
        if 'steps' in highway:
            has_stairs = True
        if not profile_cfg.stairs_allowed and has_stairs:
            return False, "Contains stairs or steps"

        # 2. Wheelchair designated tag constraint
        wc = edge_data.get('wheelchair')
        wc_access = edge_data.get('wheelchair_accessible')
        if profile_cfg.name.lower().find("wheelchair") != -1 or profile_cfg.name.lower().find("mobility") != -1:
            if wc == 'no' or wc_access is False:
                return False, "Marked as not wheelchair accessible"
            if profile_cfg.requires_wheelchair_tag and wc not in ['yes', 'designated']:
                return False, "Lacks designated wheelchair infrastructure"

        # 3. Slope constraint
        if profile_cfg.max_slope_percent is not None:
            slope = edge_data.get('slope_percent')
            if slope is not None and isinstance(slope, (int, float)):
                if slope > profile_cfg.max_slope_percent:
                    return False, f"Slope {slope:.1f}% exceeds threshold {profile_cfg.max_slope_percent:.1f}%"

        # 4. Pathway width constraint
        if profile_cfg.min_width_m > 0:
            width = edge_data.get('width_m')
            if width is not None and isinstance(width, (int, float)) and 0 < width < profile_cfg.min_width_m:
                return False, f"Width {width:.2f}m is below minimum {profile_cfg.min_width_m:.2f}m"

        # 5. Dynamic waterlogging constraint
        if u is not None and v is not None:
            water_depth = edge_data.get('water_depth', 0.0)
            if water_depth > 0:
                p_name = profile_cfg.name.lower()
                if "wheelchair" in p_name and water_depth >= 3.0:
                    return False, f"Water depth {water_depth:.1f}cm exceeds safe limit for wheelchairs (3cm)"
                elif ("elderly" in p_name or "pregnant" in p_name) and water_depth >= 5.0:
                    return False, f"Water depth {water_depth:.1f}cm exceeds safe limit for {profile_cfg.name} (5cm)"
                elif water_depth >= 8.0:
                    return False, f"Severe waterlogging ({water_depth:.1f}cm) blocks passage"

        return True, "Accessible"

    @classmethod
    def get_accessible_subgraph(cls, G: nx.Graph, profile_name: str) -> nx.Graph:
        """
        Returns a subgraph containing only edges and nodes currently feasible for the profile.
        Works seamlessly with MultiGraph and Graph.
        """
        profile_cfg = get_profile_config(profile_name)
        
        if G.is_multigraph():
            subG = nx.MultiGraph()
            # Copy node attributes
            for n, d in G.nodes(data=True):
                subG.add_node(n, **d)
                
            for u, v, k, d in G.edges(keys=True, data=True):
                accessible, _ = cls.is_edge_accessible(d, profile_cfg, u, v)
                if accessible:
                    subG.add_edge(u, v, key=k, **d)
        else:
            subG = nx.Graph()
            for n, d in G.nodes(data=True):
                subG.add_node(n, **d)
                
            for u, v, d in G.edges(data=True):
                accessible, _ = cls.is_edge_accessible(d, profile_cfg, u, v)
                if accessible:
                    subG.add_edge(u, v, **d)
                    
        return subG

subgraph_manager = AccessibleSubgraphManager()
