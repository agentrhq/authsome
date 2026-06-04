from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "authsome"


def _imports_under(package: str) -> set[str]:
    package_path = SRC / package
    imports: set[str] = set()
    for path in package_path.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("authsome."):
                        imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("authsome."):
                imports.add(node.module)
    return imports


def _assert_no_imports(package: str, forbidden: set[str]) -> None:
    imports = _imports_under(package)
    own_prefix = f"authsome.{package}"
    violations = sorted(
        module
        for module in imports
        if module != own_prefix
        and not module.startswith(f"{own_prefix}.")
        and any(module == item or module.startswith(f"{item}.") for item in forbidden)
    )
    assert violations == []


def test_auth_is_orthogonal_library_module() -> None:
    _assert_no_imports("auth", {"authsome.server", "authsome.vault", "authsome.identity"})


def test_vault_is_orthogonal_library_module() -> None:
    _assert_no_imports("vault", {"authsome.server", "authsome.auth", "authsome.identity"})


def test_identity_is_orthogonal_library_module() -> None:
    _assert_no_imports("identity", {"authsome.server", "authsome.auth", "authsome.vault", "authsome.cli"})


def test_proxy_is_leaf_injection_module() -> None:
    _assert_no_imports("proxy", {"authsome.server", "authsome.cli"})
