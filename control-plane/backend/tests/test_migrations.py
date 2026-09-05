from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def load_migration(name: str):
    path = Path(__file__).parents[1] / "alembic" / "versions" / f"{name}.py"
    spec = spec_from_file_location(name, path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_approval_uniqueness_migration_tolerates_missing_legacy_constraint(monkeypatch):
    migration = load_migration("0008_approval_project_uniqueness")
    statements = []
    constraints = []

    monkeypatch.setattr(migration.op, "execute", statements.append)
    monkeypatch.setattr(
        migration.op,
        "create_unique_constraint",
        lambda name, table, columns: constraints.append((name, table, columns)),
    )

    migration.upgrade()

    assert statements == ["ALTER TABLE approvals DROP CONSTRAINT IF EXISTS approvals_approval_id_key"]
    assert constraints == [("uq_approvals_project_approval_id", "approvals", ["project_id", "approval_id"])]
