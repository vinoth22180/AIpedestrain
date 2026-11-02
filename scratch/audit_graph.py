from src.graph_manager import load_or_build_graph

G = load_or_build_graph()
edges = list(G.edges(data=True, keys=True))

print('=== STAIRS EDGES ===')
for u,v,k,d in edges:
    if d.get('stairs'):
        print('  u=%s v=%s key=%s stairs=%s ramp=%s wheelchair=%s slope=%s length=%.1fm' % (u,v,k,d['stairs'],d.get('ramp'),d.get('wheelchair'),d.get('slope_percent'),d.get('length_m',0)))

slopes = [d.get('slope_percent', 0) for _,_,_,d in edges if d.get('slope_percent') is not None and d.get('slope_percent', 0) > 0]
if slopes:
    print('\n=== SLOPE STATS (positive values only) ===')
    print('  Count:', len(slopes))
    print('  Max: %.1f%%' % max(slopes))
    print('  Mean: %.1f%%' % (sum(slopes)/len(slopes)))
    for t in [5, 8, 10, 15]:
        count = sum(1 for s in slopes if s > t)
        print('  > %d%%: %d edges' % (t, count))

wc_vals = set()
for _,_,_,d in edges:
    wc = d.get('wheelchair')
    if wc is not None:
        wc_vals.add(str(wc))
print('\n=== WHEELCHAIR ATTRIBUTE VALUES:', wc_vals, '===')

ramp_count = sum(1 for _,_,_,d in edges if d.get('ramp'))
print('\n=== RAMP EDGES:', ramp_count, '===')

rest_count = sum(1 for _,_,_,d in edges if d.get('restricted'))
print('=== RESTRICTED EDGES:', rest_count, '===')

# Sample subway edges
print('\n=== SUBWAY EDGES (first 3) ===')
count = 0
for u,v,k,d in edges:
    if d.get('subway'):
        print('  u=%s v=%s stairs=%s wheelchair=%s slope=%.1f' % (u,v,d.get('stairs'),d.get('wheelchair'),d.get('slope_percent',0)))
        count += 1
        if count >= 3:
            break
