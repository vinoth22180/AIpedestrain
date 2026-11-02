import yaml
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'weights.yaml')
DATASETS_PATH = os.path.join(os.path.dirname(__file__), 'datasets.yaml')

def load_weights_config():
    if not os.path.exists(CONFIG_PATH):
        # Default fallback if file is missing
        return {
            'dynamic_weights': {
                'alpha_congestion': 50.0,
                'beta_predictive': 20.0,
                'gamma_signal': 30.0,
                'delta_decay': 1.0
            },
            'signal_decay': {
                'lambda_rate': 0.005,
                'epsilon': 0.1
            }
        }
        
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

def load_datasets_config():
    if not os.path.exists(DATASETS_PATH):
        return {
            "active": "vit_vellore",
            "datasets": {
                "vit_vellore": {
                    "name": "VIT Vellore Campus",
                    "center": [79.155, 12.971],
                    "zoom": 15.5,
                    "default_origin": [79.1559, 12.9692],
                    "default_destination": [79.1583, 12.9718]
                }
            }
        }
    with open(DATASETS_PATH, 'r') as f:
        return yaml.safe_load(f)

WEIGHTS_CONFIG = load_weights_config()
DATASETS_CONFIG = load_datasets_config()
