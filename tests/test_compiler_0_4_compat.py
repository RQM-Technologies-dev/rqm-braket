import sys
import pytest
if sys.version_info < (3,11): pytest.skip("rqm-compiler 0.4 requires Python 3.11+",allow_module_level=True)
from rqm_compiler import Circuit,compile_representation_aware,lower_circuit_for_backend
from rqm_braket.translator import to_backend_circuit

def test_compiler_0_4_candidate_lowers_through_braket():
 c=Circuit(2);c.h(0);c.rxx(0,1,.2);c.rzz(0,1,-.1);c.cx(0,1)
 compiled=compile_representation_aware(c)
 lowered=lower_circuit_for_backend(compiled.circuit,backend_family="braket_gate_model")
 out=to_backend_circuit(lowered,optimize=False)
 assert out is not None
 assert len(out.instructions)>0

def test_compiler_0_4_report_does_not_leak_into_descriptor_contract():
 c=Circuit(2);c.rx(0,.2);c.cx(0,1)
 compiled=compile_representation_aware(c)
 descriptors=compiled.circuit.to_descriptors()
 assert all(set(d)=={"gate","targets","controls","params"} for d in descriptors)
