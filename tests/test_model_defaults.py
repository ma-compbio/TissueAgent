"""Tests for the application-wide model default."""

import models


def test_gpt_55_is_the_default_for_both_roles() -> None:
    """Both agent roles should initialize with GPT-5.5."""
    selection = models.Selection()

    assert models.DEFAULT_MODEL_ID == "gpt-5.5"
    assert selection.orchestration == "gpt-5.5"
    assert selection.worker == "gpt-5.5"
    assert models.list_models()[0] == {
        "id": "gpt-5.5",
        "provider": "openai",
        "label": "GPT-5.5 (default)",
    }


def test_gpt_55_uses_responses_api(monkeypatch) -> None:
    """GPT-5.5 should use the endpoint recommended for tool calling."""
    monkeypatch.setattr(models, "get_api_key", lambda _provider: "test-key")

    model = models.build_chat_model("gpt-5.5", role="worker")

    assert model.use_responses_api is True
