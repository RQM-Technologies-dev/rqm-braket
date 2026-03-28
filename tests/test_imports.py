"""Smoke tests: verify that all public symbols import without error."""

import importlib.util
import os
import subprocess
import sys

import pytest
import rqm_braket


def test_package_imports() -> None:
    """The top-level package must be importable."""
    assert rqm_braket is not None


def test_version_attribute() -> None:
    """The package must expose a ``__version__`` string."""
    assert isinstance(rqm_braket.__version__, str)
    assert rqm_braket.__version__


def test_public_api_symbols() -> None:
    """All documented public symbols must be accessible."""
    # New architecture symbols
    assert rqm_braket.BraketBackend is not None
    assert rqm_braket.BraketTranslator is not None
    assert rqm_braket.RQMGate is not None
    assert callable(rqm_braket.compile_to_braket_circuit)
    assert callable(rqm_braket.run_local)
    assert callable(rqm_braket.run_device)
    assert rqm_braket.BraketResult is not None


def test_all_list_is_complete() -> None:
    """Every non-optional symbol in __all__ must exist on the package."""
    for name in rqm_braket.__all__:
        if name == "api_blueprint" and importlib.util.find_spec("flask") is None:
            continue
        assert hasattr(rqm_braket, name), f"rqm_braket.{name} not found"


def test_backward_compat_to_braket_circuit() -> None:
    """to_braket_circuit is still importable for backward compatibility."""
    from rqm_braket.translators import to_braket_circuit  # noqa: F401

    assert callable(to_braket_circuit)


def test_submodule_imports() -> None:
    """Every submodule must be importable individually."""
    import rqm_braket.backend  # noqa: F401
    import rqm_braket.circuits  # noqa: F401
    import rqm_braket.devices  # noqa: F401
    import rqm_braket.execution  # noqa: F401
    import rqm_braket.results  # noqa: F401
    import rqm_braket.translator  # noqa: F401
    import rqm_braket.translators  # noqa: F401


def test_removed_symbols_not_in_all() -> None:
    """quaternion_to_circuit is not in the public API (pending rqm-core ZYZ support).

    spinor_to_circuit and bloch_to_circuit have been re-added as thin
    delegation wrappers that delegate canonical math to rqm-core.
    """
    assert "quaternion_to_circuit" not in rqm_braket.__all__


def test_top_level_import_does_not_load_api_module() -> None:
    """Top-level import should stay Flask-free until API symbols are requested."""
    cmd = [
        sys.executable,
        "-c",
        "import sys, rqm_braket; raise SystemExit(int('rqm_braket.api' in sys.modules))",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_import_api_without_flask_has_clear_error() -> None:
    """rqm_braket.api should fail clearly when Flask is unavailable."""
    cmd = [
        sys.executable,
        "-c",
        (
            "import importlib.util; "
            "orig = importlib.util.find_spec; "
            "importlib.util.find_spec = lambda n,*a,**k: None if n=='flask' else orig(n,*a,**k); "
            "import rqm_braket; "
            "import rqm_braket.api"
        ),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)

    assert proc.returncode != 0
    message = (proc.stderr or proc.stdout)
    assert "rqm_braket.api requires Flask" in message
    assert "rqm-braket[api]" in message


def test_import_api_with_flask_succeeds() -> None:
    """rqm_braket.api import should work when Flask is installed."""
    pytest.importorskip("flask")
    import rqm_braket.api as api_module

    assert api_module.api_blueprint is not None
