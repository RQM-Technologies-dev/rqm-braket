"""
rqm_braket.backend
==================

High-level backend object that ties together translation and execution.

:class:`BraketBackend` is the primary entry point for users who want a
single object representing the AWS Braket backend.  It wraps
:class:`~rqm_braket.translator.BraketTranslator` and the
:mod:`rqm_braket.execution` helpers behind a stable, object-oriented API.
"""

from __future__ import annotations

from typing import Any, Tuple

from braket.circuits import Circuit

from rqm_braket.execution import run_device as _run_device
from rqm_braket.execution import run_local as _run_local
from rqm_braket.results import BraketResult
from rqm_braket.translator import BraketTranslator, to_backend_circuit


class BraketBackend:
    """Amazon Braket backend adapter for the RQM ecosystem.

    Provides a unified interface for:

    * translating compiled programs to Braket circuits, and
    * executing those circuits on the local simulator or AWS devices.

    Examples
    --------
    >>> from rqm_braket.backend import BraketBackend
    >>> from rqm_braket.translator import RQMGate
    >>> backend = BraketBackend()
    >>> seq = [RQMGate(gate="H", target=0), RQMGate(gate="CNOT", target=1, control=0)]
    >>> circuit = backend.compile_to_circuit(seq)
    >>> result = backend.run_local(circuit, shots=200)
    >>> print(result.counts)
    """

    def compile_to_circuit(self, compiled_program: Any) -> Circuit:
        """Translate *compiled_program* into a Braket ``Circuit``.

        Parameters
        ----------
        compiled_program:
            A ``CompiledProgram``-compatible object (has ``.instructions``)
            or a sequence of ``CompiledInstruction``-compatible objects
            (e.g. :class:`~rqm_braket.translator.RQMGate` instances).

        Returns
        -------
        braket.circuits.Circuit

        Examples
        --------
        >>> from rqm_braket.translator import RQMGate
        >>> backend = BraketBackend()
        >>> circuit = backend.compile_to_circuit([RQMGate(gate="H", target=0)])
        """
        return BraketTranslator().to_circuit(compiled_program)

    def run_local(
        self,
        program_or_circuit: Circuit | Any,
        shots: int = 100,
    ) -> BraketResult:
        """Execute *program_or_circuit* on the local Braket state-vector simulator.

        Does **not** require AWS credentials.

        Parameters
        ----------
        program_or_circuit:
            A Braket ``Circuit``, a ``CompiledProgram``-compatible object, or
            a sequence of ``CompiledInstruction``-compatible objects.
        shots:
            Number of measurement shots (default 100).

        Returns
        -------
        BraketResult
        """
        return _run_local(program_or_circuit, shots=shots)

    def run_device(
        self,
        program_or_circuit: Circuit | Any,
        device_arn: str,
        s3_folder: Tuple[str, str],
        shots: int = 100,
        **kwargs: Any,
    ) -> BraketResult:
        """Execute *program_or_circuit* on a remote AWS Braket device.

        Requires valid AWS credentials and a configured Braket-enabled region.

        Parameters
        ----------
        program_or_circuit:
            A Braket ``Circuit``, a ``CompiledProgram``-compatible object, or
            a sequence of ``CompiledInstruction``-compatible objects.
        device_arn:
            ARN of the target device.
        s3_folder:
            A ``(bucket, key_prefix)`` tuple for Braket result storage.
        shots:
            Number of measurement shots (default 100).
        **kwargs:
            Forwarded to ``AwsDevice.run()``.

        Returns
        -------
        BraketResult
        """
        return _run_device(program_or_circuit, device_arn, s3_folder, shots=shots, **kwargs)

    # ------------------------------------------------------------------
    # Compiler-integrated API (rqm-compiler required)
    # ------------------------------------------------------------------

    def compile(self, circuit: Any, optimize: bool = False) -> Circuit:
        """Compile an ``rqm_compiler.Circuit`` into a Braket ``Circuit``.

        Integrates with ``rqm-compiler``: compiles (and optionally optimizes)
        the circuit, retrieves the canonical descriptors, and translates them
        into a Braket ``Circuit``.

        Parameters
        ----------
        circuit:
            An ``rqm_compiler.Circuit`` instance.
        optimize:
            If ``True``, apply optimization passes before translation.

        Returns
        -------
        braket.circuits.Circuit

        Raises
        ------
        ImportError
            If ``rqm-compiler`` is not installed.

        Examples
        --------
        >>> # Requires rqm-compiler to be installed:
        >>> # from rqm_compiler import Circuit
        >>> # backend = BraketBackend()
        >>> # braket_circuit = backend.compile(circuit, optimize=True)
        """
        return to_backend_circuit(circuit, optimize=optimize)

    def run(
        self,
        circuit: Any,
        optimize: bool = False,
        shots: int = 1024,
        **kwargs: Any,
    ) -> BraketResult:
        """Compile and execute an ``rqm_compiler.Circuit`` on the local simulator.

        This is the primary end-to-end execution method for the compiler-first
        workflow.  It compiles the circuit (optionally optimizing it), then
        runs it on the local Braket state-vector simulator.

        Parameters
        ----------
        circuit:
            An ``rqm_compiler.Circuit`` instance.
        optimize:
            If ``True``, apply optimization passes before execution.
        shots:
            Number of measurement shots (default 1024).
        **kwargs:
            Reserved for future use.

        Returns
        -------
        BraketResult

        Raises
        ------
        ImportError
            If ``rqm-compiler`` is not installed.

        Examples
        --------
        >>> # Requires rqm-compiler to be installed:
        >>> # from rqm_compiler import Circuit
        >>> # backend = BraketBackend()
        >>> # result = backend.run(circuit, shots=512)
        >>> # print(result.to_dict())
        """
        braket_circuit = self.compile(circuit, optimize=optimize)
        return _run_local(braket_circuit, shots=shots)
