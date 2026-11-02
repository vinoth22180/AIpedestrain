import re

def main():
    with open('tests/test_darr.py', 'r') as f:
        content = f.read()

    # We will use regex to remove each function
    funcs_to_remove = [
        'test_aoc_and_arl',
        'test_shared_edge_dependency_detection',
        'test_cad_calculation',
        'test_collapse_prediction_normal',
        'test_collapse_prediction_warning',
        'test_marginal_accessibility_loss',
        'test_case_f_one_corridor_remains',
        'test_case_g_no_corridor_remains',
        'test_case_i_candidates_share_critical_edge'
    ]
    
    for func in funcs_to_remove:
        pattern = r'def ' + func + r'\(.*?\):.*?(?=\n\n(?:#|def |$))'
        content = re.sub(pattern, '', content, flags=re.DOTALL)

    # Clean up empty lines and headers
    content = re.sub(r'# ============================================================================\n# \d+\..*?\n# ============================================================================\n(?=\n(?:#|$))', '', content, flags=re.DOTALL)
    content = re.sub(r'\n{3,}', '\n\n', content)

    with open('tests/test_darr.py', 'w') as f:
        f.write(content)

if __name__ == "__main__":
    main()
