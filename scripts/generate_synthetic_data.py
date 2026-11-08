import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.main import generate, SyntheticRequest

if __name__ == '__main__':
    dataset = generate(SyntheticRequest())
    print(f"Dataset ID: {dataset['id']}")
    print(f"Known synthetic ATE: {dataset['provenance']['known_ate']:.6f}")
