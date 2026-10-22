"""Noisy simulation using IBM device noise models via Qiskit Aer."""

import inspect
from typing import Any, Dict, List, Union
from qiskit import QuantumCircuit, transpile
from qiskit.providers import Backend
import qiskit_ibm_runtime.fake_provider as fp
from qiskit_aer import AerSimulator


def list_fake_backends() -> List[str]:
    """Inspect qiskit_ibm_runtime.fake_provider, print, and return all available fake backend names.

    Returns:
        List of available fake backend class names.
    """
    backends: List[str] = []
    for name in sorted(dir(fp)):
        if name.startswith("Fake"):
            obj = getattr(fp, name)
            if inspect.isclass(obj) and issubclass(obj, Backend):
                backends.append(name)

    print("Available fake backends in qiskit_ibm_runtime.fake_provider:")
    for b in backends:
        print(f"  - {b}")
    return backends


def _resolve_backend(backend: Union[str, Any]) -> Any:
    """Resolve a backend instance from a name string or backend object."""
    if isinstance(backend, str):
        if not hasattr(fp, backend):
            available = [
                name for name in dir(fp)
                if name.startswith("Fake") and inspect.isclass(getattr(fp, name))
            ]
            raise ValueError(
                f"Fake backend '{backend}' not found in qiskit_ibm_runtime.fake_provider. "
                f"Available backends include: {available[:5]}..."
            )
        backend_cls = getattr(fp, backend)
        return backend_cls()
    return backend


def run_noisy(
    circuit: QuantumCircuit,
    backend_name: Union[str, Any] = "FakeSherbrooke",
    shots: int = 4096,
    seed: int = 42,
) -> Dict[str, int]:
    """Execute circuit under noisy simulation using IBM device noise models.

    Transpiles the circuit to the target fake backend, constructs an AerSimulator
    from the backend's noise model and configuration, and returns measurement counts.

    Args:
        circuit: Input QuantumCircuit.
        backend_name: Name of fake backend or backend instance (defaults to "FakeSherbrooke").
        shots: Number of measurement repetitions (defaults to 4096).
        seed: Random seed for reproducible transpilation and simulation (defaults to 42).

    Returns:
        Dict[str, int]: Mapping of measured bitstrings to counts.
    """
    fake_backend = _resolve_backend(backend_name)
    sim = AerSimulator.from_backend(fake_backend)

    qc = circuit.copy()
    has_measurements = any(inst.operation.name == "measure" for inst in qc.data)
    if not has_measurements:
        qc.measure_all()

    transpiled = transpile(qc, fake_backend, seed_transpiler=seed)
    result = sim.run(transpiled, shots=shots, seed_simulator=seed).result()
    return dict(result.get_counts())
