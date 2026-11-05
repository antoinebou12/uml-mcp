"""Examples exposed through ``uml://examples`` and ``uml://templates``."""

from __future__ import annotations

import json
from typing import Any


def _dump(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2)


EXAMPLE = _dump(
    {
        "title": "Decoder-only transformer",
        "subtitle": "Grouped view of a 7B parameter language model",
        "theme": "dark",
        "layers": [
            {
                "id": "tokens",
                "label": "Token IDs",
                "kind": "input",
                "shape": [2048],
                "note": "BPE token sequence",
            },
            {
                "id": "embed",
                "label": "Token embedding",
                "kind": "embedding",
                "shape": [2048, 4096],
            },
            {
                "id": "attn",
                "label": "Grouped-query attention",
                "kind": "attention",
                "shape": [32, 128],
                "repeat": 32,
                "note": "32 query heads, 8 key/value heads",
            },
            {
                "id": "ffn",
                "label": "SwiGLU feed-forward",
                "kind": "feedforward",
                "shape": [4096, 11008],
                "repeat": 32,
            },
            {
                "id": "norm",
                "label": "RMSNorm",
                "kind": "normalization",
                "shape": [4096],
            },
            {
                "id": "logits",
                "label": "Vocabulary logits",
                "kind": "output",
                "shape": [32000],
            },
        ],
        "connections": [
            {"from": "tokens", "to": "embed"},
            {"from": "embed", "to": "attn", "label": "hidden states"},
            {"from": "attn", "to": "ffn", "label": "residual stream"},
            {"from": "ffn", "to": "norm"},
            {"from": "norm", "to": "logits"},
            {
                "from": "embed",
                "to": "norm",
                "label": "residual path",
                "style": "dashed",
            },
        ],
    }
)

TEMPLATE = _dump(
    {
        "title": "Language model",
        "layers": [
            {"id": "input", "label": "Tokens", "kind": "input"},
            {
                "id": "blocks",
                "label": "Transformer block",
                "kind": "attention",
                "repeat": 12,
            },
            {"id": "output", "label": "Logits", "kind": "output"},
        ],
    }
)

#: Autoencoder in the flow layout: encoder and decoder trapezoids, a bottleneck square,
#: vector bars and a dashed skip edge that arches over the middle.
AUTOENCODER = _dump(
    {
        "title": "Autoencoder",
        "subtitle": "x is compressed to z, then reconstructed as x'",
        "layout": "flow",
        "layers": [
            {"id": "x", "label": "x", "kind": "vector", "shape": [784]},
            {"id": "enc", "label": "Encoder", "kind": "encoder", "shape": [784, 32]},
            {"id": "z", "label": "z", "kind": "bottleneck", "shape": [32]},
            {"id": "dec", "label": "Decoder", "kind": "decoder", "shape": [32, 784]},
            {"id": "xr", "label": "x'", "kind": "vector", "shape": [784]},
        ],
        "connections": [
            {"from": "x", "to": "enc"},
            {"from": "enc", "to": "z"},
            {"from": "z", "to": "dec"},
            {"from": "dec", "to": "xr"},
            {
                "from": "x",
                "to": "xr",
                "label": "ideally identical",
                "style": "dashed",
            },
        ],
    }
)

#: Encoder-decoder transformer, top down, with the repeated blocks drawn as "N×" groups.
TRANSFORMER = _dump(
    {
        "title": "Transformer",
        "subtitle": "Encoder and decoder stacks, each block repeated N times",
        "layout": "flow",
        "direction": "TB",
        "groups": [
            {"id": "enc", "label": "Encoder block", "repeat": 6, "color": "#818cf8"},
            {"id": "dec", "label": "Decoder block", "repeat": 6, "color": "#f59e0b"},
        ],
        "layers": [
            {"id": "inp", "label": "Input embedding", "kind": "embedding"},
            {
                "id": "e_attn",
                "label": "Multi-head attention",
                "kind": "attention",
                "group": "enc",
            },
            {
                "id": "e_norm1",
                "label": "Add & norm",
                "kind": "normalization",
                "group": "enc",
            },
            {
                "id": "e_ffn",
                "label": "Feed forward",
                "kind": "feedforward",
                "group": "enc",
            },
            {
                "id": "e_norm2",
                "label": "Add & norm",
                "kind": "normalization",
                "group": "enc",
            },
            {
                "id": "d_attn",
                "label": "Masked attention",
                "kind": "attention",
                "group": "dec",
            },
            {
                "id": "d_cross",
                "label": "Cross attention",
                "kind": "attention",
                "group": "dec",
            },
            {
                "id": "d_ffn",
                "label": "Feed forward",
                "kind": "feedforward",
                "group": "dec",
            },
            {"id": "lin", "label": "Linear", "kind": "output"},
            {"id": "soft", "label": "Softmax", "kind": "decision"},
        ],
        "connections": [
            {"from": "inp", "to": "e_attn"},
            {"from": "e_attn", "to": "e_norm1"},
            {"from": "e_norm1", "to": "e_ffn"},
            {"from": "e_ffn", "to": "e_norm2"},
            {"from": "e_norm2", "to": "d_attn", "label": "memory"},
            {"from": "d_attn", "to": "d_cross"},
            {"from": "d_cross", "to": "d_ffn"},
            {"from": "d_ffn", "to": "lin"},
            {"from": "lin", "to": "soft"},
            {
                "from": "e_norm2",
                "to": "d_cross",
                "label": "keys, values",
                "style": "dashed",
            },
        ],
    }
)

SAMPLES = {
    "llm_2d": (EXAMPLE, TEMPLATE),
    "llm_3d": (EXAMPLE, TEMPLATE),
}
