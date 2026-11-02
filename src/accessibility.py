import numpy as np
import pandas as pd

def _get_first(val):
    if isinstance(val, (list, tuple, np.ndarray)):
        return val[0] if len(val) > 0 else None
    return val

def extract_accessibility_features(osm_edge_row):
    """
    Takes a row (Series) from the OSM edges GeoDataFrame and 
    extracts standardized accessibility features.
    """
    features = {
        'has_stairs': False,
        'wheelchair_accessible': None, # None means unknown
        'incline_value': None,
        'surface_type': 'unknown',
        'smoothness_value': 'unknown',
        'tactile_paving': 'unknown'
    }
    
    # 1. Stairs
    highway = osm_edge_row.get('highway', '')
    if 'steps' in str(highway):
        features['has_stairs'] = True
        
    # 2. Wheelchair accessibility
    wheelchair = _get_first(osm_edge_row.get('wheelchair', None))
    if pd.notna(wheelchair):
        if wheelchair in ['yes', 'designated']:
            features['wheelchair_accessible'] = True
        elif wheelchair == 'no':
            features['wheelchair_accessible'] = False
            
    # 3. Surface & Smoothness
    surface = _get_first(osm_edge_row.get('surface', None))
    if pd.notna(surface):
        features['surface_type'] = str(surface)
        
    smoothness = _get_first(osm_edge_row.get('smoothness', None))
    if pd.notna(smoothness):
        features['smoothness_value'] = str(smoothness)
        
    # 4. Incline (parse if numeric, or qualitative like 'up', 'down')
    incline = _get_first(osm_edge_row.get('incline', None))
    if pd.notna(incline):
        try:
            # Try parse percentage string like '5%' or '5'
            features['incline_value'] = float(str(incline).replace('%', ''))
        except ValueError:
            # Could be qualitative e.g. 'up'
            features['incline_value'] = str(incline)
            
    # 5. Tactile Paving
    tactile = _get_first(osm_edge_row.get('tactile_paving', None))
    if pd.notna(tactile):
        features['tactile_paving'] = str(tactile)

    return features
