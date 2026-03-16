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
    # New architecture symbols
    assert rqm_braket.BraketBackend is not None
    assert rqm_braket.BraketTranslator is not None
    assert rqm_braket.RQMGate is not None
    assert callable(rqm_braket.compile_to_braket_circuit)
    assert callable(rqm_braket.run_local)
    assert callable(rqm_braket.run_device)
    assert rqm_braket.BraketResult is not None


def test_all_list_is_complete() -> None:
    """Every symbol in __all__ must actually exist on the package."""
    for name in rqm_braket.__all__:
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
    """spinor_to_circuit, bloch_to_circuit, quaternion_to_circuit are not
    in the public API."""
    assert "spinor_to_circuit" not in rqm_braket.__all__
    assert "bloch_to_circuit" not in rqm_braket.__all__
    assert "quaternion_to_circuit" not in rqm_braket.__all__
