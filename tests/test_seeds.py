import json
from pathlib import Path


def test_product_seed_fixtures_are_valid_and_named():
    seed_dir = Path(__file__).parents[1] / "seeds"
    names = {path.stem for path in seed_dir.glob("*.json")}
    assert {"software_labor_compression", "semiconductor_tollbooth", "tsla_replay"} <= names
    for path in seed_dir.glob("*.json"):
        assert isinstance(json.loads(path.read_text()), dict)