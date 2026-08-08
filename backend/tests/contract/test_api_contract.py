"""Guard against contract changes that would break an already-installed client.

The web deploys alongside the backend; a native app does not. A routine schema
change — removing an endpoint, or making a previously-optional field required —
silently breaks a months-old binary: with `extra="forbid"`, a new required
field returns 422, and an offline queue marks that as a permanent rejection
and loses the capture.

This test does NOT fail on **additive** changes (new endpoints, new optional
fields): those are compatible and should make no noise. It fails only on the
two **incompatible** changes that matter:

1. An operation (method + path) that existed and no longer does.
2. An operation that gains a **required** input field it didn't have.

When an incompatible change is intentional (a `/v2`, say), regenerate the
fingerprint deliberately:

    python -m tests.contract.test_api_contract

Regenerating is a conscious act, like raising a lint rule to error: the test
exists so nobody breaks the contract **by accident**.
"""

import json
from pathlib import Path

from app.main import app

_SNAPSHOT = Path(__file__).parent / "api_contract.json"
_METHODS = ("get", "post", "put", "patch", "delete")


def _required_fields(schema: dict | None, schemas: dict) -> list[str]:
    """Required body fields of one operation, resolving a $ref."""
    if not schema:
        return []
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        schema = schemas.get(name, {})
    return sorted(schema.get("required", []))


def _fingerprint() -> dict[str, list[str]]:
    """Contract fingerprint: per operation, its required input fields."""
    openapi = app.openapi()
    schemas = openapi.get("components", {}).get("schemas", {})
    ops: dict[str, list[str]] = {}
    for path, methods in openapi.get("paths", {}).items():
        for method, operation in methods.items():
            if method not in _METHODS:
                continue
            body_schema = (
                operation.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema")
            )
            ops[f"{method.upper()} {path}"] = _required_fields(body_schema, schemas)
    return ops


def _load_snapshot() -> dict[str, list[str]]:
    return json.loads(_SNAPSHOT.read_text())


def test_no_operation_was_removed():
    """Removing or renaming an operation breaks whoever called it."""
    current = _fingerprint()
    snapshot = _load_snapshot()
    removed = sorted(op for op in snapshot if op not in current)
    assert not removed, (
        "Operations removed from the contract (would break installed clients): "
        f"{removed}. If intentional (e.g. a /v2), regenerate the fingerprint: "
        "python -m tests.contract.test_api_contract"
    )


def test_no_operation_gained_a_required_field():
    """A previously-optional field turned required 422s old clients."""
    current = _fingerprint()
    snapshot = _load_snapshot()
    newly_required: dict[str, list[str]] = {}
    for op, fields in current.items():
        if op in snapshot:
            added = [f for f in fields if f not in snapshot[op]]
            if added:
                newly_required[op] = added
    assert not newly_required, (
        "Input fields now required (422 on installed clients): "
        f"{newly_required}. Make them optional with a default, or if "
        "intentional regenerate the fingerprint: "
        "python -m tests.contract.test_api_contract"
    )


def _regenerate() -> None:
    _SNAPSHOT.write_text(json.dumps(_fingerprint(), indent=2, sort_keys=True) + "\n")
    print(f"Contract fingerprint regenerated: {_SNAPSHOT}")


if __name__ == "__main__":
    _regenerate()
