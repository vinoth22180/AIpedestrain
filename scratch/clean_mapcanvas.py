import re

with open('frontend/src/components/MapCanvas.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove props
content = re.sub(r'  activeCandidateId,\n  onSelectCandidate,\n  verificationTarget,\n  verificationAnchor', '', content)

# 2. Remove verificationTarget useEffect
content = re.sub(r'  // Focus map on verification target edge.*?\[verificationTarget, routeData\]\);\n', '', content, flags=re.DOTALL)

# 3. Remove candidate route click check
candidate_click = r"""      // Check for candidate route clicks
      const candFeatures = mapRef\.current\.queryRenderedFeatures\(e\.point, {
        layers: \['candidate-routes-line'\]
      }\);
      if \(candFeatures\.length > 0 && onSelectCandidate\) {
        const clickedId = candFeatures\[0\]\.properties\.route_id;
        const matched = routeData\?\.candidate_routes\?\.find\(c => c\.route_id === clickedId\);
        if \(matched\) {
          onSelectCandidate\(matched\);
          return;
        }
      }

"""
content = content.replace(candidate_click, '')

# 4. Remove CANDIDATE_COLORS, activeSelectedId, candidatesGeoJSON, criticalEdgesGeoJSON
vars_block = r"""  const CANDIDATE_COLORS = {.*?criticalEdgesGeoJSON = \{.*?\n      \}\)\)\n  \};"""
content = re.sub(vars_block, '', content, flags=re.DOTALL)

# 5. Replace route rendering logic
# We have a big block starting from {candidatesGeoJSON.features.length > 0 ? ( down to )} before restricted segments.
# We just want the route rendering logic.
route_render = r"""            \{\/\* DARR Multi-Route Candidate Layer \*\/\}
            \{candidatesGeoJSON\.features\.length > 0 \? \(
.*?
            \) : \(
              \/\* Fallback single route \*\/
              <Source id="route-source" type="geojson" data=\{routeData\.route\}>
                <Layer \{\.\.\.routeLayerStyle\} \/>
                <Layer
                  id="route-arrows"
                  type="symbol"
                  layout=\{\{
                    'symbol-placement': 'line',
                    'symbol-spacing': 80,
                    'text-field': '>',
                    'text-font': \['Open Sans Bold', 'Arial Unicode MS Bold'\],
                    'text-size': 20,
                    'text-keep-upright': false,
                    'text-offset': \[0, -0.1\]
                  \}\}
                  paint=\{\{
                    'text-color': '#ffffff'
                  \}\}
                \/>
                <Layer
                  id="route-label"
                  type="symbol"
                  layout=\{\{
                    'symbol-placement': 'line',
                    'symbol-spacing': 400,
                    'text-field': 'DARR ROUTE',
                    'text-size': 14,
                    'text-offset': \[0, -1.5\],
                    'text-keep-upright': true
                  \}\}
                  paint=\{\{
                    'text-color': '#1d4ed8',
                    'text-halo-color': '#ffffff',
                    'text-halo-width': 2
                  \}\}
                \/>
              <\/Source>
            \)\}

            \{\/\* Critical Accessibility Bottlenecks Highlight \*\/\}
            \{criticalEdgesGeoJSON\.features\.length > 0 && \(
              <Source id="critical-corridors-source" type="geojson" data=\{criticalEdgesGeoJSON\}>
                <Layer
                  id="critical-corridors-glow"
                  type="line"
                  layout=\{\{ 'line-join': 'round', 'line-cap': 'round' \}\}
                  paint=\{\{
                    'line-color': '#ea580c',
                    'line-width': 12,
                    'line-opacity': 0.5,
                    'line-dasharray': \[2, 2\]
                  \}\}
                \/>
              <\/Source>
            \)\}"""

new_route_render = """            {/* Single Route Layer */}
            <Source id="route-source" type="geojson" data={routeData.route}>
              <Layer {...routeLayerStyle} />
              <Layer
                id="route-arrows"
                type="symbol"
                layout={{
                  'symbol-placement': 'line',
                  'symbol-spacing': 80,
                  'text-field': '>',
                  'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                  'text-size': 20,
                  'text-keep-upright': false,
                  'text-offset': [0, -0.1]
                }}
                paint={{
                  'text-color': '#ffffff'
                }}
              />
              <Layer
                id="route-label"
                type="symbol"
                layout={{
                  'symbol-placement': 'line',
                  'symbol-spacing': 400,
                  'text-field': 'ROUTE',
                  'text-size': 14,
                  'text-offset': [0, -1.5],
                  'text-keep-upright': true
                }}
                paint={{
                  'text-color': '#1d4ed8',
                  'text-halo-color': '#ffffff',
                  'text-halo-width': 2
                }}
              />
            </Source>"""

content = re.sub(route_render, new_route_render, content, flags=re.DOTALL)

# 6. Remove PCVC target edge and anchor markers
pcvc_blocks = r"""        \{\/\* PCVC Verification Target Edge Highlight \*\/\}.*?<\/Source>\n        \)\}"""
content = re.sub(pcvc_blocks, '', content, flags=re.DOTALL)

with open('frontend/src/components/MapCanvas.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
