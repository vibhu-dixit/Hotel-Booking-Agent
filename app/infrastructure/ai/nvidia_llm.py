from __future__ import annotations

from collections.abc import Iterator

from openai import OpenAI

from app.core.config import settings


def openai_client_nvidia() -> OpenAI | None:
    if not settings.nvidia_api_key:
        return None
    return OpenAI(base_url=settings.nvidia_base_url, api_key=settings.nvidia_api_key)


def stream_chat(
    *,
    messages: list[dict[str, str]],
    temperature: float = 1.0,
    top_p: float = 0.95,
    max_tokens: int = 4096,
    reasoning_budget: int | None = 16384,
    enable_thinking: bool = True,
) -> Iterator[str]:
    """Yield text chunks from NVIDIA Nemotron-style chat (streaming)."""
    client = openai_client_nvidia()
    if not client:
        raise RuntimeError("NVIDIA_API_KEY not configured")

    extra_body: dict = {
        "chat_template_kwargs": {"enable_thinking": enable_thinking},
        "reasoning_budget": reasoning_budget if reasoning_budget is not None else 16384,
    }

    stream = client.chat.completions.create(
        model=settings.nvidia_chat_model,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        extra_body=extra_body,
        stream=True,
    )

    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            yield reasoning
        if delta.content is not None:
            yield delta.content


def chat_complete(
    *,
    messages: list[dict[str, str]],
    temperature: float = 1.0,
    top_p: float = 0.95,
    max_tokens: int = 4096,
    reasoning_budget: int | None = 16384,
    enable_thinking: bool = True,
) -> str:
    """Non-streaming: concatenate streamed chunks (simplest unified surface)."""
    return "".join(
        stream_chat(
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            reasoning_budget=reasoning_budget,
            enable_thinking=enable_thinking,
        )
    )


def chat_response_text(
    *,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    top_p: float = 0.95,
    max_tokens: int = 4096,
) -> str:
    """Single assistant message (no streaming); disable thinking for JSON / tool-style replies."""
    client = openai_client_nvidia()
    if not client:
        raise RuntimeError("NVIDIA_API_KEY not configured")
    extra_body: dict = {
        "chat_template_kwargs": {"enable_thinking": False},
    }
    resp = client.chat.completions.create(
        model=settings.nvidia_chat_model,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        stream=False,
        extra_body=extra_body,
    )
    choice = resp.choices[0].message
    return (choice.content or "").strip()
