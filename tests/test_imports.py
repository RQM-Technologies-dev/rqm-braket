"""Smoke tests: verify that all public symbols import without error."""

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
    assert callable(rqm_braket.to_braket_circuit)
    assert callable(rqm_braket.run_local)
    assert callable(rqm_braket.run_device)
    assert rqm_braket.BraketResult is not None


def test_submodule_imports() -> None:
    """Every submodule must be importable individually."""
    import rqm_braket.circuits  # noqa: F401
    import rqm_braket.devices  # noqa: F401
    import rqm_braket.results  # noqa: F401
    import rqm_braket.translators  # noqa: F401
