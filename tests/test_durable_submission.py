"""Real SDK serialization with an inert session: no credentials or AWS calls."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from braket.circuits import Circuit
from rqm_braket.execution import (
    BraketDeviceError, DURABLE_SUBMISSION_CONTRACT_VERSION,
    cancel_task, get_task_metadata, run_device_async,
)

DEVICE = 'arn:aws:braket:us-west-1::device/qpu/rigetti/Cepheus-1-108Q'
ARN = 'arn:aws:braket:us-west-1:123456789012:quantum-task/task-id'


def session():
    return SimpleNamespace(region='us-west-1', create_quantum_task=Mock(return_value=ARN))


def submit(s, **kwargs):
    return run_device_async(Circuit().h(0).cnot(0, 1), DEVICE,
                            ('bucket', 'immutable/prefix'), 100,
                            aws_session=s, client_token='saved-token-123', **kwargs)


def test_real_sdk_receives_original_token_target_shots_and_output():
    s = session()
    assert DURABLE_SUBMISSION_CONTRACT_VERSION == 1
    assert submit(s) == ARN
    s.create_quantum_task.assert_called_once()
    request = s.create_quantum_task.call_args.kwargs
    assert request['clientToken'] == 'saved-token-123'
    assert request['deviceArn'] == DEVICE
    assert request['shots'] == 100
    assert request['outputS3Bucket'] == 'bucket'
    assert request['outputS3KeyPrefix'] == 'immutable/prefix'
    assert 'OPENQASM' in request['action']
    assert set(vars(s)) == {'region', 'create_quantum_task'}  # no shared mutation


def test_lost_response_never_retries_or_substitutes():
    s = session()
    s.create_quantum_task.side_effect = TimeoutError('accepted but response lost')
    with pytest.raises(BraketDeviceError):
        submit(s)
    s.create_quantum_task.assert_called_once()
    assert s.create_quantum_task.call_args.kwargs['clientToken'] == 'saved-token-123'


@pytest.mark.parametrize('overrides', [dict(client_token=''), dict(client_token=True),
    dict(client_token='a'*65), dict(client_token='invalid token'),
    dict(aws_session=None), dict(shots=0), dict(shots=True),
    dict(clientToken='old-spelling'), dict(poll_timeout_seconds=30)])
def test_invalid_durable_contract_fails_before_sdk(overrides):
    s = session()
    args = dict(aws_session=s, client_token='persisted-token', shots=100)
    args.update(overrides)
    with pytest.raises(ValueError):
        run_device_async(Circuit().h(0), DEVICE, ('bucket', 'prefix'), **args)
    s.create_quantum_task.assert_not_called()


def test_region_mismatch_never_clones_session_or_dispatches():
    s = session()
    s.region = 'us-east-1'
    with pytest.raises(ValueError):
        submit(s)
    s.create_quantum_task.assert_not_called()


def test_restart_metadata_and_cancel_only_use_saved_arn():
    s = session()
    metadata = {'quantumTaskArn': ARN, 'deviceArn': DEVICE, 'shots': 100}
    with patch('braket.aws.AwsQuantumTask') as task:
        task.return_value.metadata.return_value = metadata
        assert get_task_metadata(ARN, aws_session=s) == metadata
        task.return_value.metadata.assert_called_once_with(use_cached_value=False)
        assert cancel_task(ARN, aws_session=s) is None
        assert task.call_count == 2
        task.assert_called_with(ARN, aws_session=s)
        task.return_value.cancel.assert_called_once_with()
    s.create_quantum_task.assert_not_called()


@pytest.mark.parametrize('key', ['AMZN_BRAKET_JOB_TOKEN',
    'AMZN_BRAKET_RESERVATION_DEVICE_ARN', 'AMZN_BRAKET_RESERVATION_TIME_WINDOW_ARN'])
def test_ambient_provider_context_cannot_change_frozen_submission(monkeypatch, key):
    monkeypatch.setenv(key, 'unexpected-context')
    s = session()
    with pytest.raises(ValueError, match='ambient'):
        submit(s)
    s.create_quantum_task.assert_not_called()


def test_token_reaches_boto_create_request_without_credentials_or_network():
    from boto3 import Session
    from botocore.stub import ANY, Stubber
    from botocore.config import Config
    from braket.aws import AwsSession

    # Explicit inert test values prevent credential-chain/metadata lookup.
    boto = Session(aws_access_key_id='offline', aws_secret_access_key='offline',
                   region_name='us-west-1')
    client = boto.client('braket', config=Config(retries={'total_max_attempts': 1}))
    aws = AwsSession(boto_session=boto, braket_client=client)
    expected = dict(clientToken='saved-token-123', deviceArn=DEVICE, shots=100,
                    outputS3Bucket='bucket', outputS3KeyPrefix='immutable/prefix',
                    action=ANY, deviceParameters=ANY)
    with Stubber(client) as stub:
        stub.add_response('create_quantum_task', {'quantumTaskArn': ARN}, expected)
        assert submit(aws) == ARN
        stub.assert_no_pending_responses()


def test_frozen_action_and_correlation_tags_reach_provider():
    from rqm_braket.execution import serialize_circuit_action
    circuit = Circuit().h(0).cnot(0, 1)
    action = serialize_circuit_action(circuit)
    s = session()
    tags = {'execution_id': 'persisted-id', 'request_sha256': 'a'*64}
    submit(s, tags=tags, expected_action=action)
    request = s.create_quantum_task.call_args.kwargs
    assert request['action'] == action
    assert request['tags'] == tags


def test_changed_action_is_rejected_before_provider_dispatch():
    s = session()
    with pytest.raises(BraketDeviceError, match='Failed to submit'):
        submit(s, expected_action='different-frozen-action')
    s.create_quantum_task.assert_not_called()


@pytest.mark.parametrize('tags', [{'k': 42}, {'': 'v'}, {'k': 'v'*257}, ['bad']])
def test_bad_tags_rejected_before_submission(tags):
    s = session()
    with pytest.raises(ValueError, match='tags'):
        submit(s, tags=tags)
    s.create_quantum_task.assert_not_called()
