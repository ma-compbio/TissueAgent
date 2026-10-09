"""Limit inline image previews for benchmark-only Claude recovery runs.

Only the outgoing payload changes. Original messages, input files and generated
figures remain intact. PNG encoding avoids JPEG artifacts in scientific plots.
"""
from __future__ import annotations

import base64
from functools import lru_cache
import io
import logging
import math

from langchain_anthropic import ChatAnthropic
from PIL import Image, ImageOps

LOGGER = logging.getLogger(__name__)
MAX_EDGE = 8000
MANY_IMAGE_EDGE = 2000
MAX_ENCODED_BYTES = 9 * 1024 * 1024  # Margin below the direct API's 10 MiB.
TOTAL_IMAGE_BYTES = 24 * 1024 * 1024  # Leave space in the 32 MiB request body.


def image_blocks(content):
    """Walk content blocks, including images inside nested tool results."""
    if isinstance(content, list):
        for item in content:
            yield from image_blocks(item)
    elif isinstance(content, dict):
        if content.get('type') == 'image':
            yield content
        elif 'content' in content:
            yield from image_blocks(content['content'])


@lru_cache(maxsize=4)
def _preview(data, media_type, max_edge, byte_budget):
    raw = base64.b64decode(data, validate=True)
    with Image.open(io.BytesIO(raw)) as original:
        original_size = original.size
        if max(original_size) <= max_edge and len(data) <= byte_budget:
            return data, media_type, original_size, original_size
        # Normalize orientation before calculating the proportional resize.
        image = ImageOps.exif_transpose(original).copy()
    if image.mode not in {'RGB', 'RGBA', 'L', 'LA', 'P'}:
        image = image.convert('RGB')
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    while True:
        buffer = io.BytesIO()
        image.save(buffer, format='PNG', optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
        if len(encoded) <= byte_budget:
            return encoded, 'image/png', original_size, image.size
        if image.size == (1, 1):
            raise ValueError('Image preview cannot fit the API payload budget')
        scale = min(0.85, math.sqrt(byte_budget / len(encoded)) * 0.9)
        size = tuple(max(1, int(side * scale)) for side in image.size)
        image = image.resize(size, Image.Resampling.LANCZOS)


def normalize_image_payload(payload):
    """Copy changed branches only; do not mutate LangChain message history."""
    blocks = list(image_blocks(payload.get('messages', [])))
    if not blocks:
        return payload
    max_edge = MANY_IMAGE_EDGE if len(blocks) > 20 else MAX_EDGE
    budget = min(MAX_ENCODED_BYTES, TOTAL_IMAGE_BYTES // len(blocks))

    def convert(content):
        if isinstance(content, list):
            return [convert(item) for item in content]
        if not isinstance(content, dict):
            return content
        if content.get('type') == 'image':
            source = content.get('source', {})
            if source.get('type') != 'base64':
                return content
            data, mime, old_size, new_size = _preview(
                source['data'], source['media_type'], max_edge, budget)
            if data == source['data']:
                return content
            LOGGER.info('Claude image preview normalized: %s -> %s pixels; %s -> %s encoded bytes',
                        old_size, new_size, len(source['data']), len(data))
            return {**content, 'source': {**source, 'data': data, 'media_type': mime}}
        if 'content' in content:
            return {**content, 'content': convert(content['content'])}
        return content

    return {**payload, 'messages': convert(payload['messages'])}


class ImageSafeChatAnthropic(ChatAnthropic):
    """Apply image limits to sync, async, streaming and tool-bound requests."""

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        return normalize_image_payload(payload)
