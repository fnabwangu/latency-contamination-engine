import json
from pathlib import Path


def test_versioned_schemas_are_valid_json_objects():
    schema_dir = Path(__file__).parents[1] / "schemas"
    schemas = list(schema_dir.glob("*.schema.json"))
    assert len(schemas) >= 4
    for schema_path in schemas:
        schema = json.loads(schema_path.read_text())
        assert schema["$schema"].endswith("2020-12/schema")
        assert schema["type"] == "object"