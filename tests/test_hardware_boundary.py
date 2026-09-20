"""Offline hardware-path guards and session/restart contracts."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from braket.circuits import Circuit
from rqm_braket.execution import run_device_async, get_task_status, get_task_result
from rqm_braket.translator import BraketTranslator


def descriptor(gate, targets=None, controls=None, params=None):
    return dict(gate=gate, targets=[0] if targets is None else targets,
                controls=[] if controls is None else controls, params=params or {})


@pytest.mark.parametrize('gate,method', [('sdg','si'),('tdg','ti'),('sx','v'),('sxdg','vi'),('id','i')])
def test_named_alias(gate, method):
    assert BraketTranslator().translate_descriptors([descriptor(gate)]) == getattr(Circuit(),method)(0)


@pytest.mark.parametrize('op', [descriptor('h', [True]), descriptor('h',[-1]),
    descriptor('h',controls=[1]), descriptor('cx',[1,2],[0]),
    descriptor('rx',params={'angle':True}), descriptor('rx',params={'angle':float('nan')}),
    descriptor('rx',params={'angle':float('inf')}), descriptor('swap',[0,0]),
    descriptor('measure',controls=[1]), descriptor('su4q')])
def test_invalid_descriptors_fail_closed(op):
    with pytest.raises((ValueError, TypeError)):
        BraketTranslator().translate_descriptors([op])


def test_terminal_measurement_order_and_guards():
    translator = BraketTranslator()
    circuit = translator.translate_descriptors([descriptor('h'), descriptor('measure',[2,0,1])])
    assert [int(i.target[0]) for i in circuit.instructions if i.operator.name == 'Measure'] == [2,0,1]
    for suffix in ([descriptor('h')], [descriptor('measure',[0])]):
        with pytest.raises(ValueError):
            translator.translate_descriptors([descriptor('measure')] + suffix)


def test_session_passed_to_device_and_fresh_task_instances():
    session = object()
    raw = SimpleNamespace(measurement_counts={'101':512}, measured_qubits=[2,0,1],
                          task_metadata=SimpleNamespace(dict=lambda: {'shots':512}))
    with patch('braket.aws.AwsDevice') as device, patch('braket.aws.AwsQuantumTask') as task:
        device.return_value.run.return_value.id = 'saved-arn'
        task.return_value.state.return_value = 'COMPLETED'
        task.return_value.result.return_value = raw
        assert run_device_async(Circuit().h(0), 'device', ('bucket','prefix'), 512,
                                aws_session=session) == 'saved-arn'
        device.assert_called_once_with('device', aws_session=session)
        assert get_task_status('saved-arn', aws_session=session) == 'COMPLETED'
        result = get_task_result('saved-arn', aws_session=session)
        assert task.call_count == 2  # no process-local job map required
        assert result.measured_qubits == [2,0,1]
        assert result.counts == {'101':512}
