import re

with open('scratch/profile_route.py', 'r') as f:
    content = f.read()

# Remove imports
content = re.sub(r'from src.darr.resilience.*?\n', '', content)
content = re.sub(r'from src.darr.counterfactual.*?\n', '', content)
content = re.sub(r'from src.darr.collapse_predictor.*?\n', '', content)

# Remove the parts related to CAD, AOC, ARL, MAL, Collapse
content = re.sub(r'    # Let\'s measure CAD standalone.*?ms"\)\n', '', content, flags=re.DOTALL)

content = re.sub(r'    # 7\. AOC & ARL standalone.*?(?=    # 8\. MAL standalone)', '', content, flags=re.DOTALL)
content = re.sub(r'    # 8\. MAL standalone.*?(?=    # 9\. Collapse prediction)', '', content, flags=re.DOTALL)
content = re.sub(r'    # 9\. Collapse prediction.*?(?=    # 10\. End-to-end compute_darr_routes)', '', content, flags=re.DOTALL)

with open('scratch/profile_route.py', 'w') as f:
    f.write(content)
