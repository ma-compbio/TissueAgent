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


def test_ncbi_calls_have_bounded_reads(monkeypatch):
    """Apply the adapter's timeout to every upstream-compatible NCBI call."""
    from agents.agent_registry.genegpt_agent import runner

    observed = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"result"

    def urlopen(request, timeout):
        observed["url"] = request.full_url
        observed["timeout"] = timeout
        return Response()

    monkeypatch.setattr(runner.time, "sleep", lambda _: None)
    monkeypatch.setattr(runner.urllib.request, "urlopen", urlopen)

    assert runner._call_api("https://example.test/a b") == b"result"
    assert observed == {
        "url": "https://example.test/a+b",
        "timeout": runner._NCBI_HTTP_TIMEOUT_SECONDS,
    }
