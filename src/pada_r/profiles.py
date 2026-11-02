"""
PADA-R Profile Definitions, Hard Constraints, and Feasibility Gate
VIT SmartWalk Profile-Aware Routing Engine
"""

from typing import Tuple, Optional, Dict, Any, List

# Profile Configurable Thresholds (Technical Routing Parameters)
# Note: These are technical routing parameters designed to match campus infrastructure
# constraints and pedestrian comfort preferences, not medical advice.
PREGNANT_MAX_SLOPE = 5.0      # Maximum allowed slope percentage for pregnant profile (hard constraint)
WHEELCHAIR_MAX_SLOPE = 8.0    # Maximum allowed slope percentage for wheelchair profile (hard constraint)
ELDERLY_SLOPE_THRESHOLD = 2.5 # Slope percentage above which elderly profile receives soft effort penalty

# New Configurable Policies
PREGNANT_PROHIBIT_STAIRS = True

# Wheelchair Unknown Data Policy: "optimistic", "conservative", "strict"
# optimistic: assume unknown is accessible unless proven otherwise (e.g., stairs)
# conservative: allow unknown only if marked generally 'accessible=True' and no stairs
# strict: exclude all unknown wheelchair data
WHEELCHAIR_UNKNOWN_POLICY = "conservative"


# Centralized Profile Congestion Multipliers
# Higher values increase sensitivity to avoid crowds and high-density bottlenecks
PROFILE_CONGESTION_MULTIPLIERS = {
    "general": 1.0,     # Normal baseline congestion tolerance
    "elderly": 1.5,     # Higher congestion sensitivity to ensure comfortable, low-stress movement
    "pregnant": 1.6,    # High congestion sensitivity to avoid crowd pressure and bottlenecks
    "wheelchair": 1.7,  # Strongest congestion sensitivity to prevent stalling in dense crowds
}

PROFILE_DESCRIPTIONS = {
    "general": {
        "title": "General",
        "description": "Shortest efficient route",
        "icon": "🚶",
        "congestion_multiplier": PROFILE_CONGESTION_MULTIPLIERS["general"]
    },
    "elderly": {
        "title": "Elderly",
        "description": "Lower congestion and smoother paths",
        "icon": "👴",
        "congestion_multiplier": PROFILE_CONGESTION_MULTIPLIERS["elderly"]
    },
    "wheelchair": {
        "title": "Wheelchair",
        "description": "Avoid stairs and inaccessible paths",
        "icon": "♿",
        "congestion_multiplier": PROFILE_CONGESTION_MULTIPLIERS["wheelchair"]
    },
    "pregnant": {
        "title": "Pregnant",
        "description": "Avoid steep slopes and high congestion",
        "icon": "🤰",
        "congestion_multiplier": PROFILE_CONGESTION_MULTIPLIERS["pregnant"]
    }
}

# Normalized Weights: (Distance, Accessibility, Effort, Safety, Congestion, Predictive, Signal, Decay)
PADA_PROFILES = {
    "general": {
        "distance_weight": 1.0,
        "accessibility_weight": 0.0,
        "effort_weight": 0.0,
        "safety_weight": 0.0,
        "congestion_weight": 1.0,
        "signal_weight": 1.0,
        "decay_weight": 1.0,
        "stability_threshold": 15.0,
    },
    "wheelchair": {
        "distance_weight": 0.7,
        "accessibility_weight": 2.5,
        "effort_weight": 0.8,
        "safety_weight": 0.2,
        "congestion_weight": PROFILE_CONGESTION_MULTIPLIERS["wheelchair"],
        "signal_weight": 0.8,
        "decay_weight": 1.0,
        "stability_threshold": 10.0,
    },
    "elderly": {
        "distance_weight": 0.6, 
        "accessibility_weight": 1.2, 
        "effort_weight": 1.5, 
        "safety_weight": 1.5, 
        "congestion_weight": PROFILE_CONGESTION_MULTIPLIERS["elderly"],
        "signal_weight": 1.0,
        "decay_weight": 1.0,
        "stability_threshold": 15.0,
    },
    "pregnant": {
        "distance_weight": 0.7,
        "accessibility_weight": 1.2,
        "effort_weight": 1.2,
        "safety_weight": 1.8,
        "congestion_weight": PROFILE_CONGESTION_MULTIPLIERS["pregnant"],
        "signal_weight": 1.0,
        "decay_weight": 1.0,
        "stability_threshold": 15.0,
    }
}

BAD_SURFACES = ['cobblestone', 'unpaved', 'gravel', 'dirt', 'grass', 'sand', 'sett']
GOOD_SURFACES = ['asphalt', 'concrete', 'paved', 'paving_stones']

def _clean_val(val):
    if val is None:
        return 'unknown'
    if hasattr(val, 'iloc'):
        val = val.iloc[0]
    if isinstance(val, list) and len(val) > 0:
        val = val[0]
    return str(val).lower().strip()

def _extract_stairs(edge_data: dict) -> bool:
    has_stairs = edge_data.get('stairs', False)
    if hasattr(has_stairs, 'iloc'): has_stairs = has_stairs.iloc[0]
    if has_stairs: return True
    if edge_data.get('path_type') == 'stairs' or edge_data.get('highway') == 'steps':
        return True
    return False

def _extract_slope(edge_data: dict) -> Optional[float]:
    slope_percent = edge_data.get('slope_percent')
    if hasattr(slope_percent, 'iloc'): slope_percent = slope_percent.iloc[0]
    if slope_percent is not None:
        try:
            return float(slope_percent)
        except (ValueError, TypeError):
            return None
    return None

def is_edge_allowed(edge_data: dict, profile_name: str) -> Tuple[bool, Optional[str]]:
    """
    Evaluates profile-specific HARD CONSTRAINTS for graph edges.
    Hard constraints mean: This user profile cannot safely/usefully traverse this edge.
    Returns (is_allowed: bool, rejection_reason: Optional[str]).
    """
    profile_name = profile_name.lower() if profile_name else "general"
    if profile_name not in PADA_PROFILES:
        profile_name = "general"

    has_stairs = _extract_stairs(edge_data)
    slope_percent = _extract_slope(edge_data)

    wheelchair_val = _clean_val(edge_data.get('wheelchair'))
    accessible_val = edge_data.get('accessible')
    if hasattr(accessible_val, 'iloc'): accessible_val = accessible_val.iloc[0]
    wc_access = edge_data.get('wheelchair_accessible')
    if hasattr(wc_access, 'iloc'): wc_access = wc_access.iloc[0]

    barrier = _clean_val(edge_data.get('barrier'))
    if barrier not in ('no', 'none', 'unknown', False):
        return False, f"Physical barrier ({barrier}) blocks pedestrian passage."

    # 1. WHEELCHAIR HARD CONSTRAINTS
    if profile_name == "wheelchair":
        if has_stairs:
            return False, "Stairs are inaccessible for wheelchair users."
        if wheelchair_val == 'no' or accessible_val is False or wc_access is False:
            return False, "Path segment is marked inaccessible for wheelchair users."
        if slope_percent is not None and slope_percent > WHEELCHAIR_MAX_SLOPE:
            return False, f"Slope ({slope_percent:.1f}%) exceeds maximum wheelchair threshold ({WHEELCHAIR_MAX_SLOPE}%)."
        
        # Explicit Unknown Data Policy for Wheelchair
        is_unknown_wc = (wheelchair_val == 'unknown' and wc_access is None)
        if is_unknown_wc:
            if WHEELCHAIR_UNKNOWN_POLICY == "strict":
                return False, "Wheelchair accessibility is explicitly unknown and strict policy is active."
            elif WHEELCHAIR_UNKNOWN_POLICY == "conservative":
                if not accessible_val and not edge_data.get('ramp'):
                    return False, "Unknown wheelchair accessibility with no general accessibility indicators."

    # 2. PREGNANT HARD CONSTRAINTS
    elif profile_name == "pregnant":
        if slope_percent is not None and slope_percent > PREGNANT_MAX_SLOPE:
            return False, f"Steep slope ({slope_percent:.1f}%) exceeds configured threshold ({PREGNANT_MAX_SLOPE}%) for pregnant profile."
        if PREGNANT_PROHIBIT_STAIRS and has_stairs:
            return False, "Stairs are prohibited by the pregnant profile configuration."

    # 3. ELDERLY PROFILE
    elif profile_name == "elderly":
        # Known sloped edges are strongly discouraged via staged search and effort penalties,
        # rather than being treated as fatal hard exclusions that make the campus graph unreachable.
        pass

    # 4. GENERAL: No strict slope/stair hard exclusions beyond impassable physical barriers
    return True, None

def evaluate_feasibility(edge_data, profile_name):
    """
    Returns (status, multipliers, explanation_list)
    multipliers = {'accessibility': M_acc, 'effort': M_eff, 'safety': M_saf}
    Status can be 'FEASIBLE', 'WARNING', 'INACCESSIBLE'
    """
    profile_name = profile_name.lower() if profile_name else "general"
    if profile_name not in PADA_PROFILES:
        profile_name = "general"

    # Step 1: Check hard constraints first
    allowed, rejection_reason = is_edge_allowed(edge_data, profile_name)
    if not allowed:
        return "INACCESSIBLE", None, [rejection_reason or "Edge violated profile hard constraint."]

    has_stairs = _extract_stairs(edge_data)
    slope_percent = _extract_slope(edge_data)
    has_ramp = bool(edge_data.get('ramp', False))

    surface = _clean_val(edge_data.get('surface_type') or edge_data.get('surface'))
    smoothness = _clean_val(edge_data.get('smoothness_value'))
    tactile = _clean_val(edge_data.get('tactile_paving'))
    incline = _clean_val(edge_data.get('incline_value') or edge_data.get('slope_status'))
    wheelchair_val = _clean_val(edge_data.get('wheelchair'))
    wc_access = edge_data.get('wheelchair_accessible')
    if hasattr(wc_access, 'iloc'): wc_access = wc_access.iloc[0]
    signals = edge_data.get('signals', [])

    # Base multipliers
    m_acc = 0.0
    m_eff = 0.0
    m_saf = 0.0

    explanation = []
    status = "FEASIBLE"

    # Base Effort & Surface Calculation
    if surface in BAD_SURFACES:
        m_eff += 0.5  # 50% extra effort per meter
    elif surface in GOOD_SURFACES:
        m_eff -= 0.1  # 10% less effort

    if smoothness in ('bad', 'intermediate'):
        m_eff += 0.3

    if incline in ['up', 'down']:
        m_eff += 0.4

    # Ramp preference: reduce accessibility penalty if ramp is present
    if has_ramp:
        m_acc -= 0.5
        explanation.append("Accessible ramp preferred.")

    # Base Safety Calculation
    if len(signals) > 0:
        m_saf -= 0.4  # Reward traffic signals (safer crossing)

    if tactile == 'no':
        m_saf += 0.3  # Mild penalty for lack of tactile paving
    elif tactile == 'yes':
        m_saf -= 0.3  # Reward for tactile paving

    # Profile-Specific Soft Preferences
    if profile_name == "wheelchair":
        if surface in BAD_SURFACES:
            m_acc += 2.0
            status = "WARNING"
            explanation.append("Warning: Difficult surface for wheelchair.")
        
        # Preference for verified wheelchair-accessible edges
        is_verified_wc = (wheelchair_val == 'yes' or wc_access is True or has_ramp)
        if is_verified_wc:
            m_acc -= 1.0  # Reward verified accessibility
            m_eff -= 0.5
            explanation.append("Verified wheelchair-accessible path.")
        else:
            # Conservative preference: penalize unverified edges to steer toward verified paths
            m_acc += 0.8

    elif profile_name == "elderly":
        # Stairs: SOFT PREFERENCE -> allowed but strongly penalized
        if has_stairs:
            m_eff += 5.0
            m_acc += 2.0
            status = "WARNING"
            explanation.append("High effort penalty for stairs (elderly routing preference).")
        # Slope soft penalty: any positive slope incurs an effort penalty to prefer flat routes
        if slope_percent is not None and slope_percent > 0.0:
            slope_penalty = 1.5 * (slope_percent / 2.0)
            m_eff += slope_penalty
            status = "WARNING"
            explanation.append(f"Slope penalty ({slope_percent:.1f}%) applied for elderly comfort.")
        if surface in BAD_SURFACES:
            m_eff += 0.8
            status = "WARNING"
            explanation.append("Unpaved surface penalty for elderly profile.")

    elif profile_name == "pregnant":
        # Stairs: SOFT PREFERENCE -> high effort/safety penalty
        if has_stairs:
            m_eff += 4.0
            m_saf += 2.0
            status = "WARNING"
            explanation.append("Effort and safety penalty for stairs (pregnant routing preference).")
        # Mild slopes below max threshold
        if slope_percent is not None and slope_percent > 2.5:
            m_eff += 1.0 * (slope_percent / 2.5)
            status = "WARNING"
            explanation.append(f"Incline penalty ({slope_percent:.1f}%) applied.")

    elif profile_name == "general":
        if has_stairs:
            m_eff += 0.2  # Minimal nominal effort penalty for stairs

    multipliers = {
        'accessibility': max(0.0, m_acc),
        'effort': max(0.0, m_eff),
        'safety': max(0.0, m_saf)
    }

    return status, multipliers, explanation
