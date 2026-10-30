"""Thin wrapper around Nebius Token Factory (OpenAI-compatible) for NVIDIA Nemotron models."""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
# Fast model for drafting/triage, stronger model for escalation when stuck.
DEFAULT_FAST_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
DEFAULT_STRONG_MODEL = "nvidia/nemotron-3-super-120b-a12b"

# Backup provider: NVIDIA API catalog (build.nvidia.com), same OpenAI-compatible API.
PROVIDERS = {
    "nebius": {"base_url": DEFAULT_BASE_URL, "key_env": "NEBIUS_API_KEY",
               "fast": DEFAULT_FAST_MODEL, "strong": DEFAULT_STRONG_MODEL},
    "nvidia": {"base_url": "https://integrate.api.nvidia.com/v1", "key_env": "NVIDIA_API_KEY",
               "fast": "nvidia/nemotron-3.5-lightning-30b-a3b", "strong": "nvidia/nemotron-3.5-super-vl-120b-a12b"},
}


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    by_model: dict = field(default_factory=dict)

    def add(self, model: str, prompt: int, completion: int, secs: float) -> None:
        self.calls += 1
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.seconds += secs
        self.by_model[model] = self.by_model.get(model, 0) + 1


class NemotronClient:
    """Calls Nemotron on Nebius Token Factory. Model IDs are overridable by env vars."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 fast_model: str | None = None, strong_model: str | None = None):
        from openai import OpenAI  # imported lazily so tests can run without a key

        name = os.environ.get("TESTPILOT_PROVIDER")
        if not name:
            name = "nvidia" if (os.environ.get("NVIDIA_API_KEY") and not os.environ.get("NEBIUS_API_KEY")) else "nebius"
        prov = PROVIDERS.get(name.lower(), PROVIDERS["nebius"])
        self.provider = name.lower()
        key = api_key or os.environ.get(prov["key_env"])
        if not key:
            raise RuntimeError("Set NEBIUS_API_KEY (tokenfactory.nebius.com) or NVIDIA_API_KEY (build.nvidia.com).")
        default_url = os.environ.get("NEBIUS_BASE_URL") if self.provider == "nebius" else None
        self.client = OpenAI(base_url=base_url or default_url or prov["base_url"], api_key=key)
        self.fast_model = fast_model or os.environ.get("TESTPILOT_FAST_MODEL", prov["fast"])
        self.strong_model = strong_model or os.environ.get("TESTPILOT_STRONG_MODEL", prov["strong"])
        self.usage = Usage()

    def chat(self, system: str, user: str, strong: bool = False, temperature: float = 0.2) -> str:
        model = self.strong_model if strong else self.fast_model
        start = time.time()
        resp = self.client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=int(os.environ.get("TESTPILOT_MAX_TOKENS", "8192")),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        u = getattr(resp, "usage", None)
        self.usage.add(model, getattr(u, "prompt_tokens", 0) or 0,
                       getattr(u, "completion_tokens", 0) or 0, time.time() - start)
        return resp.choices[0].message.content or ""


_THINK = re.compile(r"<think>.*?</think>", re.S)
_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


def extract_code(text: str) -> str:
    """Pull the Python code out of a model reply (strips reasoning and fences)."""
    text = _THINK.sub("", text)
    blocks = _FENCE.findall(text)
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    return text.strip() + "\n"
