# ACCESSIBILITY ENRICHMENT REPORT
**VIT Vellore Accessibility-Aware Dynamic Pedestrian Rerouting System**

## 1. MAPPED ACCESSIBILITY FEATURES
The current dataset possesses limited verified accessibility attributes. No features were artificially fabricated during this audit. Missing data is preserved as `unknown` or stripped where unparseable.

- **Stairs**: 7 edges verified as stairs (`True`).
- **Ramps**: 0 edges verified.
- **Slopes/Inclines**: 0 edges contain usable numerical slopes. All values were stripped by the `build_final_dataset.py` string-parsing failure.
- **Surfaces**: 65% of the graph is unknown. The known surfaces on test routes are predominantly asphalt.

## 2. MANUAL VIT LOCATIONS
Authoritative coordinates have been strictly preserved and verified for spatial accuracy.
- MGR = [79.15583638463455, 12.969035851408112]
- SMV = [79.15766374408548, 12.969246074425618]
- TT = [79.15953483469843, 12.97082312983498]
- SJT = [79.16394473901578, 12.970917609834906]
- PRP = [79.16640540870385, 12.971264636436771]
- Gandhi Block = [79.16799249061337, 12.972225506107774]
- CTS = [79.15623259923282, 12.970266027390673]
- Anna Auditorium = [79.1556603675251, 12.96984326294177]
- Parking Lot = [79.1550150327412, 12.968647332768128]

## 3. MISSING REAL-WORLD DATA REQUIREMENTS
To achieve physically differentiated personalized routing, the following real-world data must be mapped:
1. **Slope gradients**: `Elderly` and `Pregnant` profiles rely entirely on avoiding high-effort inclines.
2. **Ramps**: Wheelchair accessibility requires ramps to traverse elevations without stairs.
3. **Surface texturing**: Dirt vs asphalt distinctions are required to trigger Wheelchair physical penalties. 
Without this data, the algorithm relies solely on distance and the 7 available stair blockades.
