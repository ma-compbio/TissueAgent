"""Offline checks for uncapped pilot execution and terminal response handling."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


spec = importlib.util.spec_from_file_location(
    'lohoff_pilot', Path(__file__).resolve().parents[1] / 'benchmark/run_lohoff_architecture_pilot.py'
)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


@pytest.mark.parametrize('metadata', [
    {'finish_reason': 'length'},
    {'stop_reason': 'max_tokens'},
    {'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'}},
])
def test_empty_truncated_response_is_not_completion(metadata):
    message = SimpleNamespace(content='', response_metadata=metadata)
    with pytest.raises(pilot.ResponseTruncated):
        pilot.check_response_complete(message)


def test_normal_tool_call_and_completed_response_are_allowed():
    for reason in ('tool_calls', 'stop'):
        pilot.check_response_complete(SimpleNamespace(response_metadata={'finish_reason': reason}))
    with pytest.raises(pilot.ResponseTruncated):
        pilot.check_response_complete(SimpleNamespace(response_metadata={}), {'finish_reason': 'length'})


def test_controller_keeps_waiting_beyond_former_wall_budget(tmp_path, monkeypatch):
    pilot.dump(tmp_path / 'manifest.json', {'source_hashes': {}, 'input_hashes': {}})
    pilot.dump(tmp_path / 'preflight/full/result.json', {'status': 'offline_preflight_passed'})
    clock = [0]

    def elapse(_):
        clock[0] += 3600

    process = Mock(pid=123, returncode=1)
    process.poll.side_effect = [None, None, 1, 1]
    kill = Mock()
    monkeypatch.setattr(pilot, 'ARMS', ('full',))
    monkeypatch.setattr(pilot, 'credentials', lambda: None)
    monkeypatch.setattr(pilot, 'score_all', lambda _: None)
    monkeypatch.setattr(pilot.subprocess, 'Popen', lambda *args, **kwargs: process)
    monkeypatch.setattr(pilot.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(pilot.time, 'sleep', elapse)
    monkeypatch.setattr(pilot.os, 'killpg', kill)

    pilot.controller(tmp_path)

    result = json.loads((tmp_path / 'runs/full/result.json').read_text())
    assert result['elapsed_seconds'] == 7200
    assert result['status'] == 'worker_failed'
    kill.assert_not_called()
    assert json.loads((tmp_path / 'status.json').read_text())['status'] == 'complete'
