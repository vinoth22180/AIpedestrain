import pandas as pd
import numpy as np

csv_path = r'C:\Users\nares\.gemini\antigravity-ide\brain\993324a8-8220-4d77-b60d-58d33afc78ef\.user_uploaded\media_1788972526228.csv'
df = pd.read_csv(csv_path)

print(f"Total rows: {len(df)}")
print(f"Columns: {list(df.columns)}")
print(f"Unique from_nodes: {df['from_node'].nunique()}")
print(f"Unique to_nodes: {df['to_node'].nunique()}")
print(f"Unique way_ids: {df['way_id'].nunique()}")

path_types = df['highway'].value_counts(dropna=False).to_dict()
print(f"Path types (highway): {path_types}")

names = df['name'].dropna().unique()
print(f"Names count: {len(names)}, Examples: {names[:5]}")

stairs = df['stairs'].value_counts(dropna=False).to_dict() if 'stairs' in df.columns else 'N/A'
print(f"Stairs (bool): {stairs}")
steps_count = df[df['highway'] == 'steps'].shape[0] if 'highway' in df.columns else 0
print(f"Steps (highway=steps): {steps_count}")

ramps = df['ramp'].value_counts(dropna=False).to_dict() if 'ramp' in df.columns else 'N/A'
print(f"Ramps: {ramps}")

crossings = df['crossing'].value_counts(dropna=False).to_dict() if 'crossing' in df.columns else 'N/A'
print(f"Crossings: {crossings}")

slopes = df['slope'].value_counts(dropna=False).to_dict() if 'slope' in df.columns else 'N/A'
print(f"Slope fields: {slopes}")

surfaces = df['surface'].value_counts(dropna=False).to_dict() if 'surface' in df.columns else 'N/A'
print(f"Surfaces: {surfaces}")

access = df['access'].value_counts(dropna=False).to_dict() if 'access' in df.columns else 'N/A'
foot_access = df['foot_access'].value_counts(dropna=False).to_dict() if 'foot_access' in df.columns else 'N/A'
print(f"Access: {access}")
print(f"Foot Access: {foot_access}")

wheelchair = df['wheelchair'].value_counts(dropna=False).to_dict() if 'wheelchair' in df.columns else 'N/A'
print(f"Wheelchair: {wheelchair}")

has_geom = any(col in df.columns for col in ['geometry', 'lat', 'lon', 'latitude', 'longitude'])
print(f"Coordinates/Geometry present: {has_geom}")
