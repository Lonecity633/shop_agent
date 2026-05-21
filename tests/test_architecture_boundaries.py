from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _python_files(*parts: str):
    base = ROOT.joinpath(*parts)
    return [path for path in base.rglob("*.py") if "__pycache__" not in path.parts]


def _assert_absent(paths: list[Path], forbidden: list[str]) -> None:
    violations = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                violations.append(f"{path.relative_to(ROOT)} contains {needle}")
    assert not violations, "\n".join(violations)


def test_agent_does_not_import_backend_or_local_business_implementation():
    _assert_absent(
        _python_files("app", "agent"),
        [
            "from app.backend",
            "import app.backend",
            "from app.mcp_server.tools",
            "from app.models",
            "from app.crud",
            "from app.db",
            "from app.services",
            "from app.agent.tools",
            "sqlalchemy",
            "AsyncSessionLocal",
            "get_db",
        ],
    )


def test_backend_does_not_import_agent_or_mcp_server():
    _assert_absent(
        _python_files("app", "backend"),
        ["from app.agent", "import app.agent", "from app.mcp_server", "import app.mcp_server"],
    )


def test_mcp_server_does_not_import_agent_or_backend_implementation():
    _assert_absent(
        _python_files("app", "mcp_server"),
        [
            "from app.agent",
            "import app.agent",
            "from app.backend",
            "import app.backend",
            "from app.models",
            "from app.crud",
            "from app.db",
            "from app.services",
            "sqlalchemy",
            "AsyncSessionLocal",
            "get_db",
        ],
    )


def test_old_top_level_backend_packages_are_removed():
    old_backend_packages = ["api", "services", "crud", "models", "schemas", "db", "core"]
    leftovers = [name for name in old_backend_packages if ROOT.joinpath("app", name).exists()]
    assert not leftovers, f"old top-level backend packages still exist: {leftovers}"
