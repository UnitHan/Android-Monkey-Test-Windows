"""The committed openapi.json IS the contract. Any API change must update it deliberately:

uv run python scripts/export_openapi.py
"""

import json
from pathlib import Path

from contract import ContractClient

SNAPSHOT = Path(__file__).resolve().parents[2] / "openapi.json"


def test_openapi_matches_committed_contract(api: ContractClient) -> None:
    assert SNAPSHOT.exists(), "run scripts/export_openapi.py to create openapi.json"
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert api.spec == committed, "API contract drift: re-export openapi.json and review the diff"


def test_every_operation_documents_problem_errors(api: ContractClient) -> None:
    for path, ops in api.spec["paths"].items():
        for method, op in ops.items():
            assert "500" in op["responses"], f"{method.upper()} {path} must document 500 problem+json"
            if any(p["in"] == "path" for p in op.get("parameters", [])):
                assert "404" in op["responses"] or "422" in op["responses"], f"{method.upper()} {path}"
