"""Debug why corsair tokens aren't merging."""
import json
import numpy as np
from pathlib import Path

# Load corsair tokens metadata
metadata_file = Path("layers/warcom/extracted/corsair-voidscarred/tokens/tokens_metadata.json")
with open(metadata_file) as f:
    data = json.load(f)

tokens = data["tokens"]
areas = [t["area"] for t in tokens]

print(f"Total tokens: {len(tokens)}")
print(f"\nToken areas:")
for t in tokens:
    print(f"  {t['filename']}: {t['area']} (bbox: {t['bbox']})")

# Calculate median from top 60%
sorted_areas = sorted(areas, reverse=True)
top_60_count = max(1, int(len(sorted_areas) * 0.6))
median_area = np.median(sorted_areas[:top_60_count])
print(f"\nSorted areas: {sorted_areas}")
print(f"Top 60% count: {top_60_count}")
print(f"Top 60% areas: {sorted_areas[:top_60_count]}")
print(f"Median of top 60%: {median_area}")

# Check token02 and token03
token02 = tokens[1]  # index 1
token03 = tokens[2]  # index 2

print(f"\nToken02:")
print(f"  Area: {token02['area']} ({token02['area']/median_area*100:.1f}% of median)")
print(f"  Undersized (<70%)? {token02['area'] < median_area * 0.7}")

print(f"\nToken03:")
print(f"  Area: {token03['area']} ({token03['area']/median_area*100:.1f}% of median)")
print(f"  Undersized (<70%)? {token03['area'] < median_area * 0.7}")

# Calculate distance
x1 = token02['bbox']['x']
y1 = token02['bbox']['y']
w1 = token02['bbox']['width']
h1 = token02['bbox']['height']

x2 = token03['bbox']['x']
y2 = token03['bbox']['y']
w2 = token03['bbox']['width']
h2 = token03['bbox']['height']

# Distance calculation
if x1 + w1 < x2:
    dx = x2 - (x1 + w1)
elif x2 + w2 < x1:
    dx = x1 - (x2 + w2)
else:
    dx = 0

if y1 + h1 < y2:
    dy = y2 - (y1 + h1)
elif y2 + h2 < y1:
    dy = y1 - (y2 + h2)
else:
    dy = 0

distance = (dx**2 + dy**2)**0.5
median_size = np.sqrt(median_area)
scaled_distance = median_size * 0.3

print(f"\nDistance calculation:")
print(f"  Token02 bbox: x={x1}, y={y1}, w={w1}, h={h1}")
print(f"  Token03 bbox: x={x2}, y={y2}, w={w2}, h={h2}")
print(f"  dx={dx}, dy={dy}")
print(f"  Distance: {distance}")
print(f"  Median size: {median_size:.1f}")
print(f"  Scaled distance threshold (30%): {scaled_distance:.1f}")
print(f"  Should merge (distance < threshold)? {distance < scaled_distance}")

# Size similarity
area_ratio = max(token02['area'], token03['area']) / min(token02['area'], token03['area'])
print(f"\nSize similarity:")
print(f"  Area ratio: {area_ratio:.2f}")
print(f"  Similar enough (<3.0)? {area_ratio < 3.0}")

# Merged aspect ratio
merge_x = min(x1, x2)
merge_y = min(y1, y2)
merge_w = max(x1 + w1, x2 + w2) - merge_x
merge_h = max(y1 + h1, y2 + h2) - merge_y
merged_aspect = max(merge_w, merge_h) / min(merge_w, merge_h)

print(f"\nMerged result:")
print(f"  Merged bbox: x={merge_x}, y={merge_y}, w={merge_w}, h={merge_h}")
print(f"  Merged aspect ratio: {merged_aspect:.2f}")
print(f"  Reasonable aspect (<2.5)? {merged_aspect < 2.5}")

print(f"\n{'='*60}")
print(f"SHOULD MERGE? {token02['area'] < median_area * 0.7 or token03['area'] < median_area * 0.7} (at least one undersized)")
print(f"  AND distance={distance:.1f} < {scaled_distance:.1f}? {distance < scaled_distance}")
print(f"  AND area_ratio={area_ratio:.2f} < 3.0? {area_ratio < 3.0}")
print(f"  AND aspect={merged_aspect:.2f} < 2.5? {merged_aspect < 2.5}")
all_checks = (
    (token02['area'] < median_area * 0.7 or token03['area'] < median_area * 0.7) and
    distance < scaled_distance and
    area_ratio < 3.0 and
    merged_aspect < 2.5
)
print(f"\nALL CHECKS PASS? {all_checks}")
