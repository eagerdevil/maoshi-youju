import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.vendor'))
sys.path.insert(0,str(ROOT))

import pytest

@pytest.fixture(autouse=True)
def isolate_model_credentials(monkeypatch,tmp_path):
    """Unit tests must never read local paid-service credentials or call a live model."""
    from backend import services
    monkeypatch.setattr(services,'CONFIG',tmp_path/'test-model-not-configured.json')
