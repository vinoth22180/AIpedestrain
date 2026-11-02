import React, { useEffect, useRef, useState, useMemo } from 'react';
import Map, { Source, Layer, Popup } from 'react-map-gl/maplibre';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

export default function MapCanvas({
  routeData,
  activeCandidateId,
  onSelectCandidate,
  refreshTrigger,
  isMapSelectionMode,
  selectedMapLocation,
  onMapLocationSelected,
  showPedestrianNetwork = true,
  resizeTrigger
}) {
  const mapRef = useRef();
  const containerRef = useRef(null);

  // Auto-resize MapLibre whenever container size changes or panel toggles
  useEffect(() => {
    const handleResize = () => {
      if (mapRef.current) {
        const map = mapRef.current.getMap ? mapRef.current.getMap() : mapRef.current;
        if (map && typeof map.resize === 'function') {
          map.resize();
        }
      }
    };

    handleResize();
    const timer = setTimeout(handleResize, 300);
    return () => clearTimeout(timer);
  }, [resizeTrigger]);

  useEffect(() => {
    if (!containerRef.current || typeof window.ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => {
      if (mapRef.current) {
        const map = mapRef.current.getMap ? mapRef.current.getMap() : mapRef.current;
        if (map && typeof map.resize === 'function') {
          map.resize();
        }
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);
  
  // Default map view centered on VIT Vellore Campus
  const [viewState, setViewState] = useState({
    longitude: 79.155,
    latitude: 12.971,
    zoom: 15.5,
    pitch: 45,
    bearing: 0
  });

  const [configLoaded, setConfigLoaded] = useState(false);
  const [academicBlocks, setAcademicBlocks] = useState(null);
  const [pedestrianNetwork, setPedestrianNetwork] = useState(null);
  const [popupInfo, setPopupInfo] = useState(null);
  const [congestedAreas, setCongestedAreas] = useState([]);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/config')
      .then(res => res.json())
      .then(cfg => {
        if (cfg.center) {
          setViewState(prev => ({
            ...prev,
            longitude: cfg.center[0],
            latitude: cfg.center[1],
            zoom: cfg.zoom || 15.5
          }));
        }
        setConfigLoaded(true);
      })
      .catch(console.error);
    fetch('http://127.0.0.1:8000/api/academic_blocks')
      .then(res => res.json())
      .then(data => {
        setAcademicBlocks(data);
      })
      .catch(console.error);

    fetch('http://127.0.0.1:8000/api/pedestrian_network')
      .then(res => res.json())
      .then(setPedestrianNetwork)
      .catch(console.error);
  }, []);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/congestion/map')
      .then(res => res.json())
      .then(data => {
        if (data.congested_areas) setCongestedAreas(data.congested_areas);
      })
      .catch(console.error);
  }, [refreshTrigger]);

  // Handle subtle basemap road label de-cluttering when the style loads
  const handleMapLoad = (evt) => {
    try {
      const map = evt.target;
      const style = map.getStyle();
      if (style && style.layers) {
        style.layers.forEach(layer => {
          // Dim background OSM road labels so they do not compete with campus pedestrian network
          if (layer.id && (layer.id.includes('road_label') || layer.id.includes('road-label') || layer.id.includes('label_road'))) {
            map.setPaintProperty(layer.id, 'text-opacity', 0.35);
          }
        });
      }
    } catch (err) {
      console.warn('Could not adjust basemap style:', err);
    }
  };

  // Congestion on Academic Blocks (Points)
  const congestionAreaGeoJson = useMemo(() => {
    if (!academicBlocks || !congestedAreas || congestedAreas.length === 0) {
      return { type: 'FeatureCollection', features: [] };
    }
    const features = [];
    congestedAreas.forEach(area => {
      const block = academicBlocks.features.find(
        f => f.properties.short_name === area.location || f.properties.name === area.location
      );
      if (block && area.congestion_score > 0.02 && area.status !== 'expired') {
        let trend_indicator = '';
        let pred_level = '';
        if (area.prediction && area.prediction.prediction_available) {
          pred_level = area.prediction.predicted_level;
          if (area.prediction.trend === 'INCREASING') trend_indicator = '↑';
          else if (area.prediction.trend === 'DECREASING') trend_indicator = '↓';
          else trend_indicator = '→';
        }

        features.push({
          type: 'Feature',
          geometry: block.geometry,
          properties: {
            ...area,
            congestion_level: (area.congestion_level === 'SEVERE' || area.congestion_level === 'HIGH') ? 'HIGH' :
                              (area.congestion_level === 'MODERATE' || area.congestion_level === 'MEDIUM') ? 'MEDIUM' : 'LOW',
            trend_indicator,
            pred_level,
            color: (area.congestion_level === 'SEVERE' || area.congestion_level === 'HIGH') ? '#dc2626' : 
                   (area.congestion_level === 'MODERATE' || area.congestion_level === 'MEDIUM') ? '#f59e0b' : '#10b981'
          }
        });
      }
    });
    return { type: 'FeatureCollection', features };
  }, [academicBlocks, congestedAreas]);

  // Congestion on Pedestrian Graph Edges (Lines)
  const congestionEdgeGeoJson = useMemo(() => {
    if (!pedestrianNetwork || !congestedAreas || congestedAreas.length === 0) {
      return { type: 'FeatureCollection', features: [] };
    }
    const features = [];
    const addedKeys = new Set();

    congestedAreas.forEach(area => {
      const targetEdgeIds = new Set(area.edge_ids || []);
      targetEdgeIds.add(area.location);

      pedestrianNetwork.features.forEach(edge => {
        const edgeId = edge.properties.edge_id;
        if (targetEdgeIds.has(edgeId) && area.congestion_score > 0.02 && area.status !== 'expired') {
          const featureKey = `${edgeId}_${area.location}`;
          if (!addedKeys.has(featureKey)) {
            addedKeys.add(featureKey);
            const normLevel = (area.congestion_level === 'SEVERE' || area.congestion_level === 'HIGH') ? 'HIGH' :
                              (area.congestion_level === 'MODERATE' || area.congestion_level === 'MEDIUM') ? 'MEDIUM' : 'LOW';
            const normColor = normLevel === 'HIGH' ? '#dc2626' : normLevel === 'MEDIUM' ? '#f59e0b' : '#10b981';
            features.push({
              type: 'Feature',
              geometry: edge.geometry,
              properties: {
                ...edge.properties,
                ...area,
                congestion_level: normLevel,
                color: normColor
              }
            });
          }
        }
      });
    });
    return { type: 'FeatureCollection', features };
  }, [pedestrianNetwork, congestedAreas]);

  // Selected Path for Congestion Analysis (highlight before/after video upload)
  const selectedEdgeGeoJson = useMemo(() => {
    if (!selectedMapLocation || !selectedMapLocation.geometry) return null;
    return {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: selectedMapLocation.geometry,
          properties: {
            edge_id: selectedMapLocation.edge_id,
            display_name: selectedMapLocation.display_name || 'Selected Pedestrian Path'
          }
        }
      ]
    };
  }, [selectedMapLocation]);

  // Active Route Geometry
  const activeRouteData = useMemo(() => {
    if (!routeData) return null;
    return routeData.candidate_routes?.find(c => c.route_id === activeCandidateId)?.geojson || routeData.route;
  }, [routeData, activeCandidateId]);

  // Auto-fit route bounds when route changes
  useEffect(() => {
    if (activeRouteData && mapRef.current) {
      const coords = activeRouteData.geometry?.coordinates;
      if (coords && coords.length > 0) {
        const bounds = coords.reduce(
          (acc, coord) => [
            [Math.min(acc[0][0], coord[0]), Math.min(acc[0][1], coord[1])],
            [Math.max(acc[1][0], coord[0]), Math.max(acc[1][1], coord[1])]
          ],
          [[coords[0][0], coords[0][1]], [coords[0][0], coords[0][1]]]
        );
        
        if (!routeData?.isBackground) {
          mapRef.current.fitBounds(bounds, { 
            padding: { top: 120, bottom: 250, left: 450, right: 400 }, 
            duration: 1500 
          });
        }
      }
    }
  }, [activeRouteData, routeData?.isBackground]);

  // Candidate alternative routes
  const candidateRoutesGeoJson = useMemo(() => {
    if (!routeData?.candidate_routes || routeData.candidate_routes.length === 0) return null;
    const currentActiveId = activeCandidateId || routeData.selected_candidate?.route_id || 'recommended';
    return {
      type: 'FeatureCollection',
      features: routeData.candidate_routes.map(cand => ({
        ...cand.geojson,
        properties: {
          ...cand.geojson.properties,
          route_id: cand.route_id,
          isActive: cand.route_id === currentActiveId
        }
      }))
    };
  }, [routeData, activeCandidateId]);

  // Map Click Handling
  const handleMapClick = (e) => {
    if (!mapRef.current) return;

    if (isMapSelectionMode) {
      // Query rendered features including the base, casing, and feature lines
      const edgeFeatures = mapRef.current.queryRenderedFeatures(e.point, {
        layers: [
          'pedestrian-network-base', 'pedestrian-network-casing',
          'pedestrian-network-restricted',
          'pedestrian-network-slopes-line', 'pedestrian-network-crossings-line',
          'pedestrian-network-barriers-line', 'pedestrian-network-subways-line',
          'pedestrian-network-stairs-line', 'pedestrian-network-ramps-line'
        ]
      });
      
      if (edgeFeatures.length > 0 && onMapLocationSelected) {
        // Prioritize edge on active route if user clicked on or near the route line
        let selectedFeature = edgeFeatures[0];
        const activeEdgeIds = new Set();
        if (routeData?.stats?.path_edges) {
          routeData.stats.path_edges.forEach(e => {
            if (e.edge_id) activeEdgeIds.add(e.edge_id);
          });
        }
        
        const routeMatch = edgeFeatures.find(f => activeEdgeIds.has(f.properties.edge_id));
        if (routeMatch) {
          selectedFeature = routeMatch;
        } else if (edgeFeatures.length > 1) {
          // Select geometrically closest edge to the click point
          const clickLng = e.lngLat.lng;
          const clickLat = e.lngLat.lat;
          let minDistance = Infinity;
          edgeFeatures.forEach(f => {
            if (f.geometry && f.geometry.coordinates) {
              const coords = f.geometry.type === 'LineString' ? f.geometry.coordinates : f.geometry.coordinates.flat();
              coords.forEach(([lng, lat]) => {
                const d = Math.hypot(lng - clickLng, lat - clickLat);
                if (d < minDistance) {
                  minDistance = d;
                  selectedFeature = f;
                }
              });
            }
          });
        }

        const edge_id = selectedFeature.properties.edge_id;
        const display_name = selectedFeature.properties.display_name || selectedFeature.properties.name || "Campus Walkway";
        
        onMapLocationSelected({
          edge_id,
          display_name,
          longitude: e.lngLat.lng,
          latitude: e.lngLat.lat,
          geometry: selectedFeature.geometry
        });
      } else if (onMapLocationSelected) {
        alert("No nearby pedestrian path found. Please click directly on or near a pedestrian path.");
      }
      return;
    }

    // Check for candidate route clicks
    const candFeatures = mapRef.current.queryRenderedFeatures(e.point, {
      layers: ['candidate-routes-line', 'candidate-routes-casing']
    });
    if (candFeatures.length > 0 && onSelectCandidate) {
      const clickedId = candFeatures[0].properties.route_id;
      const matched = routeData?.candidate_routes?.find(c => c.route_id === clickedId);
      if (matched) {
        onSelectCandidate(matched);
        return;
      }
    }

    // Check for academic block clicks
    const blockFeatures = mapRef.current.queryRenderedFeatures(e.point, {
      layers: ['academic-blocks-marker', 'academic-blocks-label']
    });
    if (blockFeatures.length > 0) {
      const feature = blockFeatures[0];
      setPopupInfo({
        longitude: e.lngLat.lng,
        latitude: e.lngLat.lat,
        name: feature.properties.name,
        short_name: feature.properties.short_name
      });
    } else {
      setPopupInfo(null);
    }
  };

  const cursorStyle = isMapSelectionMode ? 'crosshair' : 'grab';
  const networkVisibility = showPedestrianNetwork ? 'visible' : 'none';

  return (
    <div ref={containerRef} style={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: 0 }}>
      {/* Selection Mode Prompt Bar */}
      {isMapSelectionMode && (
        <div style={{
          position: 'absolute',
          top: '20px',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 20,
          backgroundColor: '#1e293b',
          color: '#ffffff',
          padding: '8px 20px',
          borderRadius: '24px',
          boxShadow: '0 4px 14px rgba(0,0,0,0.25)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          fontSize: '0.85rem',
          fontWeight: '600',
          letterSpacing: '0.02em',
          pointerEvents: 'none'
        }}>
          <span style={{ fontSize: '16px' }}>📍</span>
          <span>Click any pedestrian path on the map to select it for video analysis</span>
        </div>
      )}

      <Map
        ref={mapRef}
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        onClick={handleMapClick}
        onLoad={handleMapLoad}
        mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
        mapLibre={maplibregl}
        style={{ width: '100%', height: '100%' }}
        cursor={cursorStyle}
        interactiveLayerIds={[
          'academic-blocks-marker', 'academic-blocks-label',
          'candidate-routes-line', 'candidate-routes-casing',
          'pedestrian-network-base', 'pedestrian-network-casing',
          'pedestrian-network-restricted',
          'pedestrian-network-slopes-line', 'pedestrian-network-crossings-line',
          'pedestrian-network-barriers-line', 'pedestrian-network-subways-line',
          'pedestrian-network-stairs-line', 'pedestrian-network-ramps-line'
        ]}
      >
        {/* Background Pedestrian Network Source & Layers */}
        {pedestrianNetwork && pedestrianNetwork.features.length > 0 && (
          <Source id="pedestrian-network-source" type="geojson" data={pedestrianNetwork}>
            
            {/* White Underlay Casing: Creates sharp contrast against basemap road fills & tiles */}
            <Layer
              id="pedestrian-network-casing"
              type="line"
              filter={['match', ['get', 'highway'], ['footway', 'pedestrian', 'path', 'service', 'residential', 'unclassified', 'track', 'steps', 'living_street'], true, false]}
              layout={{
                'line-join': 'round',
                'line-cap': 'round',
                'visibility': networkVisibility
              }}
              paint={{
                'line-color': '#ffffff',
                'line-width': ['interpolate', ['linear'], ['zoom'], 13, 2.5, 15, 4.8, 16, 6.2, 17, 8.2, 18, 11],
                'line-opacity': 0.85
              }}
            />

            {/* Standard Campus Pedestrian Walkways: High-contrast, clean slate style */}
            <Layer
              id="pedestrian-network-base"
              type="line"
              filter={['match', ['get', 'highway'], ['footway', 'pedestrian', 'path', 'service', 'residential', 'unclassified', 'track', 'steps', 'living_street'], true, false]}
              layout={{
                'line-join': 'round',
                'line-cap': 'round',
                'visibility': networkVisibility
              }}
              paint={{
                'line-color': '#334155', // Slate-700: visible, elegant, distinct from basemap roads
                'line-width': ['interpolate', ['linear'], ['zoom'], 13, 1.5, 15, 3.2, 16, 4.2, 17, 5.8, 18, 7.5],
                'line-opacity': 0.95
              }}
            />
            
            {/* Perimeter / Major Vehicular Roads: Distinct subtle dashed pattern */}
            <Layer
              id="pedestrian-network-restricted"
              type="line"
              filter={['match', ['get', 'highway'], ['primary', 'secondary', 'tertiary'], true, false]}
              layout={{
                'line-join': 'round',
                'line-cap': 'round',
                'visibility': networkVisibility
              }}
              paint={{
                'line-color': '#94a3b8', // slate-400
                'line-width': ['interpolate', ['linear'], ['zoom'], 13, 1.2, 15, 2.2, 17, 3.5, 18, 5.0],
                'line-dasharray': [3, 2],
                'line-opacity': 0.75
              }}
            />
            
            {/* Slopes Base Line */}
            <Layer
              id="pedestrian-network-slopes-line"
              type="line"
              filter={[
                'any',
                ['in', ['get', 'slope_status'], ['literal', ['up', 'down']]],
                ['all',
                  ['==', ['get', 'slope_status'], 'measured'],
                  ['>', ['get', 'slope_percent'], 4]
                ]
              ]}
              layout={{
                'line-join': 'round',
                'line-cap': 'round',
                'visibility': networkVisibility
              }}
              paint={{
                'line-color': '#7c3aed', // purple-600
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 3, 16, 4.5, 18, 7],
                'line-opacity': 1.0
              }}
            />
            
            {/* Crossings Base Line */}
            <Layer
              id="pedestrian-network-crossings-line"
              type="line"
              filter={['!=', 'crossing', 'no']}
              layout={{
                'line-join': 'round',
                'line-cap': 'round',
                'visibility': networkVisibility
              }}
              paint={{
                'line-color': '#0284c7', // sky-600
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 3, 16, 4.5, 18, 7],
                'line-dasharray': [2, 2],
                'line-opacity': 0.95
              }}
            />
            
            {/* Barriers Base Line */}
            <Layer
              id="pedestrian-network-barriers-line"
              type="line"
              filter={['!=', 'barrier', 'no']}
              layout={{
                'line-join': 'round',
                'line-cap': 'round',
                'visibility': networkVisibility
              }}
              paint={{
                'line-color': '#dc2626', // red-600
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 3, 16, 4.5, 18, 7],
                'line-opacity': 0.95
              }}
            />
            
            {/* Subways Base Line */}
            <Layer
              id="pedestrian-network-subways-line"
              type="line"
              filter={['==', 'subway', true]}
              layout={{
                'line-join': 'round',
                'line-cap': 'round',
                'visibility': networkVisibility
              }}
              paint={{
                'line-color': '#0891b2', // cyan-600
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 3.5, 16, 5, 18, 8],
                'line-dasharray': [1, 2],
                'line-opacity': 1.0
              }}
            />
            
            {/* Stairs Base Line */}
            <Layer
              id="pedestrian-network-stairs-line"
              type="line"
              filter={['==', 'stairs', true]}
              layout={{
                'line-join': 'round',
                'line-cap': 'round',
                'visibility': networkVisibility
              }}
              paint={{
                'line-color': '#b45309', // amber-700
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 3.5, 16, 5, 18, 8],
                'line-dasharray': [0.5, 0.5],
                'line-opacity': 1.0
              }}
            />
            
            {/* Ramps Base Line */}
            <Layer
              id="pedestrian-network-ramps-line"
              type="line"
              filter={['==', 'ramp', true]}
              layout={{
                'line-join': 'round',
                'line-cap': 'round',
                'visibility': networkVisibility
              }}
              paint={{
                'line-color': '#059669', // emerald-600
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 3.5, 16, 5, 18, 8],
                'line-opacity': 1.0
              }}
            />

            {/* Feature Symbols: only show when zoomed in (minzoom: 16.8) to prevent campus-level clutter */}
            <Layer
              id="feature-labels"
              type="symbol"
              minzoom={16.8}
              filter={[
                'any',
                ['==', 'subway', true],
                ['==', 'stairs', true],
                ['==', 'ramp', true],
                ['!=', 'crossing', 'no'],
                ['!=', 'barrier', 'no'],
                ['in', ['get', 'slope_status'], ['literal', ['up', 'down']]],
                ['all',
                  ['==', ['get', 'slope_status'], 'measured'],
                  ['>', ['get', 'slope_percent'], 4]
                ]
              ]}
              layout={{
                'symbol-placement': 'line',
                'symbol-spacing': ['interpolate', ['linear'], ['zoom'], 16.8, 300, 18, 150],
                'text-field': [
                  'case',
                  ['==', ['get', 'subway'], true], '⬇ SUBWAY',
                  ['==', ['get', 'stairs'], true], '🪜 STAIRS',
                  ['==', ['get', 'ramp'], true], '♿ RAMP',
                  ['!=', ['get', 'barrier'], 'no'], '🚧 BARRIER',
                  ['!=', ['get', 'crossing'], 'no'], '🚸 CROSSING',
                  ['==', ['get', 'slope_status'], 'measured'], ['concat', '↗ ', ['get', 'slope_percent'], '% SLOPE'],
                  ['==', ['get', 'slope_status'], 'up'], '↗ UPHILL',
                  ['==', ['get', 'slope_status'], 'down'], '↘ DOWNHILL',
                  ''
                ],
                'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                'text-size': 11,
                'text-max-angle': 45,
                'text-pitch-alignment': 'viewport',
                'text-keep-upright': true,
                'text-allow-overlap': false,
                'visibility': networkVisibility
              }}
              paint={{
                'text-color': '#1e293b',
                'text-halo-color': '#ffffff',
                'text-halo-width': 2.5
              }}
            />
            
            {/* Standard Edge Labels: only visible when closely zoomed in (minzoom: 17) */}
            <Layer
              id="pedestrian-edge-labels"
              type="symbol"
              minzoom={17.0}
              filter={[
                'all',
                ['has', 'display_name'],
                ['!=', ['get', 'subway'], true],
                ['!=', ['get', 'stairs'], true],
                ['!=', ['get', 'ramp'], true],
                ['==', ['get', 'crossing'], 'no'],
                ['==', ['get', 'barrier'], 'no']
              ]}
              layout={{
                'symbol-placement': 'line',
                'text-field': ['get', 'display_name'],
                'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
                'text-size': 11,
                'text-max-angle': 45,
                'text-pitch-alignment': 'viewport',
                'text-keep-upright': true,
                'symbol-spacing': 350,
                'visibility': networkVisibility
              }}
              paint={{
                'text-color': '#475569',
                'text-halo-color': '#ffffff',
                'text-halo-width': 2.5
              }}
            />
          </Source>
        )}

        {/* Academic Blocks: Landmark Pins and Short Badge Labels */}
        {academicBlocks && academicBlocks.features.length > 0 && (
          <Source id="academic-blocks-source" type="geojson" data={academicBlocks}>
            {/* Landmark Marker Pin */}
            <Layer
              id="academic-blocks-marker"
              type="circle"
              paint={{
                'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 5, 16, 7, 18, 9],
                'circle-color': '#1e293b',
                'circle-stroke-width': 2,
                'circle-stroke-color': '#ffffff'
              }}
            />
            {/* Readable Landmark Label: Clean short badge, subtle halo, no collisions */}
            <Layer
              id="academic-blocks-label"
              type="symbol"
              layout={{
                'symbol-placement': 'point',
                'text-field': ['get', 'short_name'],
                'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                'text-size': ['interpolate', ['linear'], ['zoom'], 14, 11, 16, 12, 18, 14],
                'text-anchor': 'top',
                'text-offset': [0, 0.7],
                'text-allow-overlap': false,
                'text-optional': true
              }}
              paint={{
                'text-color': '#0f172a',
                'text-halo-color': '#ffffff',
                'text-halo-width': 2.5,
                'text-halo-blur': 0.5
              }}
            />
          </Source>
        )}

        {/* Academic Block Info Popup */}
        {popupInfo && (
          <Popup
            longitude={popupInfo.longitude}
            latitude={popupInfo.latitude}
            anchor="bottom"
            offset={[0, -12]}
            onClose={() => setPopupInfo(null)}
            closeOnClick={false}
          >
            <div style={{ padding: '6px', textAlign: 'center', minWidth: '130px' }}>
              <strong style={{ fontSize: '14px', display: 'block', color: '#1e293b' }}>
                {popupInfo.short_name}
              </strong>
              <span style={{ fontSize: '12px', color: '#64748b', display: 'block', marginTop: '2px' }}>
                {popupInfo.name}
              </span>
              <div style={{ fontSize: '10px', marginTop: '4px', color: '#3b82f6', fontWeight: '600' }}>
                Campus Academic Block
              </div>
            </div>
          </Popup>
        )}

        {/* Congestion on Pedestrian Graph Edges */}
        {congestionEdgeGeoJson && congestionEdgeGeoJson.features.length > 0 && (
          <Source id="congestion-edge-source" type="geojson" data={congestionEdgeGeoJson}>
            {/* Red Danger Glow Aura */}
            <Layer
              id="congestion-edge-glow"
              type="line"
              layout={{ 'line-join': 'round', 'line-cap': 'round' }}
              paint={{
                'line-color': ['get', 'color'],
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 10, 18, 18],
                'line-opacity': 0.4,
                'line-blur': 3
              }}
            />
            {/* White separator casing */}
            <Layer
              id="congestion-edge-casing"
              type="line"
              layout={{ 'line-join': 'round', 'line-cap': 'round' }}
              paint={{
                'line-color': '#ffffff',
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 6, 18, 12],
                'line-opacity': 0.95
              }}
            />
            {/* Dashed Red Warning Line */}
            <Layer
              id="congestion-edge-line"
              type="line"
              layout={{ 'line-join': 'round', 'line-cap': 'round' }}
              paint={{
                'line-color': ['get', 'color'],
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 4, 18, 8],
                'line-dasharray': [2, 1]
              }}
            />
            <Layer
              id="congestion-edge-label"
              type="symbol"
              layout={{
                'symbol-placement': 'line',
                'text-field': [
                  'concat', 
                  '⚠ ', ['get', 'congestion_level'], ' CONGESTION'
                ],
                'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                'text-size': 11,
                'text-offset': [0, -1.2],
                'text-keep-upright': true
              }}
              paint={{
                'text-color': ['get', 'color'],
                'text-halo-color': '#ffffff',
                'text-halo-width': 2.5
              }}
            />
          </Source>
        )}

        {/* Congestion on Academic Block Areas (Pulse Circles) */}
        {congestionAreaGeoJson && congestionAreaGeoJson.features.length > 0 && (
          <Source id="congestion-area-source" type="geojson" data={congestionAreaGeoJson}>
            <Layer
              id="congestion-layer-pulse"
              type="circle"
              paint={{
                'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 25, 18, 110],
                'circle-color': ['get', 'color'],
                'circle-opacity': 0.2,
                'circle-blur': 0.8
              }}
            />
            <Layer
              id="congestion-layer"
              type="circle"
              paint={{
                'circle-radius': ['interpolate', ['linear'], ['zoom'], 14, 15, 18, 65],
                'circle-color': ['get', 'color'],
                'circle-opacity': 0.45,
                'circle-stroke-width': 2,
                'circle-stroke-color': ['get', 'color'],
                'circle-blur': 0.2
              }}
            />
            <Layer
              id="congestion-label"
              type="symbol"
              layout={{
                'text-field': [
                  'concat',
                  ['get', 'location'], '\n',
                  ['get', 'congestion_level'], ' CONGESTION'
                ],
                'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                'text-size': 11,
                'text-offset': [0, 0]
              }}
              paint={{
                'text-color': '#ffffff',
                'text-halo-color': ['get', 'color'],
                'text-halo-width': 2.5
              }}
            />
          </Source>
        )}

        {/* Map-Selected Edge Highlight (during congestion map selection mode) */}
        {selectedEdgeGeoJson && (
          <Source id="selected-edge-source" type="geojson" data={selectedEdgeGeoJson}>
            {/* Amber Glow Aura */}
            <Layer
              id="selected-edge-glow"
              type="line"
              layout={{ 'line-join': 'round', 'line-cap': 'round' }}
              paint={{
                'line-color': '#f59e0b',
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 14, 18, 22],
                'line-opacity': 0.45,
                'line-blur': 3
              }}
            />
            {/* Crisp White Casing */}
            <Layer
              id="selected-edge-casing"
              type="line"
              layout={{ 'line-join': 'round', 'line-cap': 'round' }}
              paint={{
                'line-color': '#ffffff',
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 8, 18, 14],
                'line-opacity': 1.0
              }}
            />
            {/* High-visibility Amber Core */}
            <Layer
              id="selected-edge-line"
              type="line"
              layout={{ 'line-join': 'round', 'line-cap': 'round' }}
              paint={{
                'line-color': '#d97706',
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 5, 18, 9]
              }}
            />
            <Layer
              id="selected-edge-label"
              type="symbol"
              layout={{
                'symbol-placement': 'line',
                'text-field': '📍 SELECTED FOR ANALYSIS',
                'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                'text-size': 12,
                'text-offset': [0, -1.3],
                'text-keep-upright': true
              }}
              paint={{
                'text-color': '#b45309',
                'text-halo-color': '#ffffff',
                'text-halo-width': 3
              }}
            />
          </Source>
        )}

        {/* Candidate Alternative Routes */}
        {candidateRoutesGeoJson && candidateRoutesGeoJson.features.length > 0 && (
          <Source id="candidate-routes-source" type="geojson" data={candidateRoutesGeoJson}>
            <Layer
              id="candidate-routes-casing"
              type="line"
              filter={['!=', 'isActive', true]}
              layout={{ 'line-join': 'round', 'line-cap': 'round' }}
              paint={{
                'line-color': '#ffffff',
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 7, 18, 13],
                'line-opacity': 0.85
              }}
            />
            <Layer
              id="candidate-routes-line"
              type="line"
              filter={['!=', 'isActive', true]}
              layout={{ 'line-join': 'round', 'line-cap': 'round' }}
              paint={{
                'line-color': '#6366f1', // indigo-500
                'line-width': ['interpolate', ['linear'], ['zoom'], 14, 4, 18, 8],
                'line-opacity': 0.8,
                'line-dasharray': [3, 2]
              }}
            />
          </Source>
        )}

        {/* Active Route Layer (Rendered on top with clear white casing and royal blue core) */}
        {activeRouteData && (
          <>
            <Source id="route-source" type="geojson" data={activeRouteData}>
              {/* Outer High-Contrast White Casing */}
              <Layer
                id="route-casing"
                type="line"
                layout={{ 'line-join': 'round', 'line-cap': 'round' }}
                paint={{
                  'line-color': '#ffffff',
                  'line-width': ['interpolate', ['linear'], ['zoom'], 14, 9, 16, 12, 18, 18],
                  'line-opacity': 1.0
                }}
              />
              {/* Dark Outline Edge for Razor-Sharp Visibility */}
              <Layer
                id="route-underlay"
                type="line"
                layout={{ 'line-join': 'round', 'line-cap': 'round' }}
                paint={{
                  'line-color': '#1e3a8a', // dark blue-900
                  'line-width': ['interpolate', ['linear'], ['zoom'], 14, 7, 16, 9.5, 18, 15],
                  'line-opacity': 0.8
                }}
              />
              {/* Vibrant Royal Blue Route Line */}
              <Layer
                id="route"
                type="line"
                layout={{ 'line-join': 'round', 'line-cap': 'round' }}
                paint={{
                  'line-color': '#2563eb', // blue-600
                  'line-width': ['interpolate', ['linear'], ['zoom'], 14, 5, 16, 7.5, 18, 12],
                  'line-opacity': 1.0
                }}
              />
              {/* Direction Indicator Chevrons */}
              <Layer
                id="route-arrows"
                type="symbol"
                layout={{
                  'symbol-placement': 'line',
                  'symbol-spacing': 90,
                  'text-field': '>',
                  'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                  'text-size': 16,
                  'text-keep-upright': false,
                  'text-offset': [0, -0.05]
                }}
                paint={{
                  'text-color': '#ffffff',
                  'text-opacity': 0.95
                }}
              />
              {/* Prominent Route Label */}
              <Layer
                id="route-label"
                type="symbol"
                layout={{
                  'symbol-placement': 'line',
                  'symbol-spacing': 350,
                  'text-field': 'WALKING ROUTE',
                  'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                  'text-size': 12,
                  'text-offset': [0, -1.4],
                  'text-keep-upright': true
                }}
                paint={{
                  'text-color': '#1e3a8a',
                  'text-halo-color': '#ffffff',
                  'text-halo-width': 2.5
                }}
              />
            </Source>

            {/* Restricted Segments on Route, if any */}
            {routeData?.restricted_segments?.features?.length > 0 && (
              <Source id="restricted-source" type="geojson" data={routeData.restricted_segments}>
                <Layer
                  id="restricted-segments"
                  type="line"
                  layout={{ 'line-join': 'round', 'line-cap': 'round' }}
                  paint={{
                    'line-color': '#dc2626',
                    'line-width': 8,
                    'line-opacity': 0.9,
                    'line-dasharray': [2, 2]
                  }}
                />
              </Source>
            )}

            {/* Origin (Start) Marker */}
            {activeRouteData?.geometry?.coordinates?.[0] && (
              <Source id="origin-source" type="geojson" data={{
                type: 'Feature',
                geometry: {
                  type: 'Point',
                  coordinates: activeRouteData.geometry.coordinates[0]
                }
              }}>
                <Layer
                  id="origin-marker-pulse"
                  type="circle"
                  paint={{
                    'circle-radius': 16,
                    'circle-color': '#ffffff',
                    'circle-opacity': 0.7
                  }}
                />
                <Layer
                  id="origin-marker-ring"
                  type="circle"
                  paint={{
                    'circle-radius': 10,
                    'circle-color': '#10b981',
                    'circle-stroke-width': 2.5,
                    'circle-stroke-color': '#ffffff'
                  }}
                />
                <Layer
                  id="origin-marker-center"
                  type="circle"
                  paint={{
                    'circle-radius': 4,
                    'circle-color': '#ffffff'
                  }}
                />
                <Layer
                  id="origin-label"
                  type="symbol"
                  layout={{
                    'text-field': 'START',
                    'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                    'text-size': 11,
                    'text-offset': [0, 1.8],
                    'text-anchor': 'top'
                  }}
                  paint={{
                    'text-color': '#065f46',
                    'text-halo-color': '#ffffff',
                    'text-halo-width': 3
                  }}
                />
              </Source>
            )}

            {/* Destination Marker */}
            {activeRouteData?.geometry?.coordinates?.length > 1 && (
              <Source id="dest-source" type="geojson" data={{
                type: 'Feature',
                geometry: {
                  type: 'Point',
                  coordinates: activeRouteData.geometry.coordinates[activeRouteData.geometry.coordinates.length - 1]
                }
              }}>
                <Layer
                  id="dest-marker-pulse"
                  type="circle"
                  paint={{
                    'circle-radius': 16,
                    'circle-color': '#ffffff',
                    'circle-opacity': 0.7
                  }}
                />
                <Layer
                  id="dest-marker-ring"
                  type="circle"
                  paint={{
                    'circle-radius': 10,
                    'circle-color': '#ef4444',
                    'circle-stroke-width': 2.5,
                    'circle-stroke-color': '#ffffff'
                  }}
                />
                <Layer
                  id="dest-marker-center"
                  type="circle"
                  paint={{
                    'circle-radius': 4,
                    'circle-color': '#ffffff'
                  }}
                />
                <Layer
                  id="dest-label"
                  type="symbol"
                  layout={{
                    'text-field': 'DESTINATION',
                    'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                    'text-size': 11,
                    'text-offset': [0, 1.8],
                    'text-anchor': 'top'
                  }}
                  paint={{
                    'text-color': '#991b1b',
                    'text-halo-color': '#ffffff',
                    'text-halo-width': 3
                  }}
                />
              </Source>
            )}
          </>
        )}
      </Map>
    </div>
  );
}
