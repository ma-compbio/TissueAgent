"""Validate real Claude payload shapes and preserve original image artifacts."""
import base64
import copy
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmark'))
import anthropic_images as images


def block(image):
    buf = io.BytesIO()
    image.save(buf, 'PNG')
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
            'data': base64.b64encode(buf.getvalue()).decode()}}


def dimensions(image_block):
    with Image.open(io.BytesIO(base64.b64decode(image_block['source']['data']))) as im:
        return im.size


def test_tool_image_is_resized_without_mutating_history_or_files(tmp_path):
    image = Image.new('RGB', (8100, 81), 'white')
    path = tmp_path / 'full_resolution.png'
    image.save(path)
    original_bytes = path.read_bytes()
    b = block(image)
    b['cache_control'] = {'type': 'ephemeral'}
    messages = [HumanMessage('inspect'), AIMessage('', tool_calls=[
        {'name': 'read_image', 'args': {}, 'id': 'call1'}]),
        ToolMessage([b], tool_call_id='call1')]
    before = copy.deepcopy(messages)
    model = images.ImageSafeChatAnthropic(model='claude-sonnet-4-5-20250929', api_key='test')
    payload = model._get_request_payload(messages)
    output = list(images.image_blocks(payload['messages']))[0]
    assert dimensions(output) == (8000, 80)
    # LangChain strips image-level cache metadata during its own conversion;
    # our transport normalizer preserves metadata present in its input.
    direct = images.normalize_image_payload({'messages': [{'content': [b]}]})
    assert direct['messages'][0]['content'][0]['cache_control'] == b['cache_control']
    assert payload['messages'][-1]['content'][0]['tool_use_id'] == 'call1'
    assert messages == before
    assert path.read_bytes() == original_bytes


def test_history_and_tool_images_count_toward_many_image_limit():
    b = block(Image.new('RGB', (2400, 120), 'white'))
    payload = {'messages': [{'role': 'user', 'content': [b] * 20},
                           {'role': 'user', 'content': [{'type': 'tool_result',
                            'tool_use_id': 'x', 'content': [b]}]}]}
    output = images.normalize_image_payload(payload)
    assert len(list(images.image_blocks(output['messages']))) == 21
    assert all(dimensions(v) == (2000, 100) for v in images.image_blocks(output['messages']))
    assert dimensions(b) == (2400, 120)


def test_oversized_encoded_payload_is_reduced_with_lossless_png_encoding():
    noise = np.random.default_rng(1).integers(0, 256, size=(1650, 1650, 3), dtype=np.uint8)
    b = block(Image.fromarray(noise))
    assert len(b['source']['data']) > 10 * 1024 * 1024
    result = images.normalize_image_payload({'messages': [{'role': 'user', 'content': [b]}]})
    output = list(images.image_blocks(result['messages']))[0]
    assert len(output['source']['data']) <= images.MAX_ENCODED_BYTES
    assert output['source']['media_type'] == 'image/png'
    assert dimensions(output)[0] < 1650


def test_aggregate_image_budget_and_small_image_passthrough(monkeypatch):
    b = block(Image.new('RGB', (20, 20), 'white'))
    assert images.normalize_image_payload({'messages': [{'content': [b]}]})['messages'][0]['content'][0] == b
    noise = np.random.default_rng(2).integers(0, 256, size=(100, 100, 3), dtype=np.uint8)
    b = block(Image.fromarray(noise))
    monkeypatch.setattr(images, 'TOTAL_IMAGE_BYTES', 30000)
    result = images.normalize_image_payload({'messages': [{'content': [b, b, b]}]})
    assert sum(len(v['source']['data']) for v in images.image_blocks(result['messages'])) <= 30000


def test_openai_style_data_uri_is_normalized_after_provider_conversion():
    b = block(Image.new('RGB', (81, 8100), 'white'))
    uri = 'data:image/png;base64,' + b['source']['data']
    message = HumanMessage([{'type': 'image_url', 'image_url': {'url': uri}}])
    model = images.ImageSafeChatAnthropic(model='claude-sonnet-4-5-20250929', api_key='test')
    result = model._get_request_payload([message], tools=[{'name': 'example', 'input_schema': {'type': 'object'}}])
    assert dimensions(next(images.image_blocks(result['messages']))) == (80, 8000)
    assert result['tools'][0]['name'] == 'example'
    assert message.content[0]['image_url']['url'] == uri


def test_recovery_bootstrap_installs_adapter_only_during_worker(monkeypatch):
    import langchain_anthropic
    import run_lohoff_claude_image_worker as worker
    original = langchain_anthropic.ChatAnthropic
    observed = []

    def fake_worker(path, run_name):
        assert path.endswith('run_lohoff_architecture_pilot.py')
        assert run_name == '__main__'
        observed.append(langchain_anthropic.ChatAnthropic)

    monkeypatch.setattr(worker.runpy, 'run_path', fake_worker)
    worker.main()
    assert observed == [images.ImageSafeChatAnthropic]
    assert langchain_anthropic.ChatAnthropic is original
