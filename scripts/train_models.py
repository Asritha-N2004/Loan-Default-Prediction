import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.main import train, DatasetRequest

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset_id')
    args = parser.parse_args()
    result = train(DatasetRequest(dataset_id=args.dataset_id))
    print(f"Model ID: {result['id']}")
    print({name: {k: m[k] for k in ['roc_auc', 'pr_auc', 'brier']} for name, m in result['models'].items()})
