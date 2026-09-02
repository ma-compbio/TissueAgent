"""Tests for GeneGPT upstream module isolation."""

import sys


def test_upstream_import_restores_tissueagent_config():
    """Restore the app config module and Python path after importing upstream."""
    import config as app_config
    from agents.agent_registry.genegpt_agent import runner

    upstream_path = str(runner._UPSTREAM_DIR)
    path_was_present = upstream_path in sys.path

    get_prompt_header, call_api = runner._import_upstream_helpers()

    assert sys.modules["config"] is app_config
    assert callable(get_prompt_header)
    assert callable(call_api)
    assert (upstream_path in sys.path) is path_was_present
