# Phase 2 Weather Impact Rules

These deterministic rules define how live weather data affects pedestrian route cost calculations.

## 1. Precipitation & Surface Interaction

**Condition:** `precipitation > 0`
**Edge factor:** Surface type interaction.

- **Unpaved / Dirt / Ground / Compacted surfaces:** 
  - *Modifier:* Penalty is multiplied by a profile-specific unpaved surface sensitivity factor.
  - *Reason:* Unpaved paths become muddy and slippery, making pedestrian traversal and wheelchair navigation significantly more difficult.
- **Asphalt / Paved / Paving Stones:**
  - *Modifier:* Normal rain penalty (x1.0).
  - *Reason:* Standard paved paths drain well and are less affected by light rain.
- **Unknown surfaces:**
  - *Modifier:* Normal rain penalty (x1.0).
  - *Reason:* We do not automatically assume worst-case conditions for unverified surfaces.

## 2. Extreme Heat Interaction

**Condition:** `apparent_temperature > 35.0 °C`
**Edge factor:** Distance.

- *Modifier:* A flat heat penalty is scaled by the distance of the edge and profile-specific heat sensitivity.
- *Reason:* Extreme heat increases traversal effort.

## 3. Profile-Specific algorithmic Sensitivities

Weather impact is scaled according to user profile to simulate diverse needs conservatively:

- **General**: Base sensitivity (x1.0 for rain and heat, x1.5 for unpaved-wet).
- **Elderly**: Increased sensitivity (x1.5 for rain, x1.3 for heat, x2.0 for unpaved-wet).
- **Pregnant**: Increased sensitivity (x1.3 for rain, x1.4 for heat, x1.8 for unpaved-wet).
- **Wheelchair**: Highly sensitive to muddy terrain (x3.0 for unpaved-wet), moderate sensitivity to rain/heat (x1.2 / x1.1).

*(Note: These are configurable algorithmic weights, not absolute medical facts.)*
