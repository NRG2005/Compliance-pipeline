"""
Minimal GPT API client for local L3 development.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List
from urllib import request
from urllib.error import HTTPError

from config import load_project_env

load_project_env()


def is_openai_configured() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def _extract_text_from_chat_response(payload: Dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("No choices returned from GPT API.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    text_content = ""
    if isinstance(content, str):
        text_content = content
    elif isinstance(content, list):
        text_parts: List[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        text_content = "\n".join(text_parts)
    else:
        raise ValueError("Unable to extract text content from GPT API response.")
        
    text_content = text_content.strip()
    if text_content.startswith("```"):
        lines = text_content.splitlines()
        valid_lines = [line for line in lines if not line.strip().startswith("```")]
        text_content = "\n".join(valid_lines).strip()
    return text_content


def _call_openai(
    base_url: str,
    api_key: str,
    chosen_model: str,
    system_prompt: str,
    user_prompt: str,
) -> Dict[str, Any]:
    """Attempt OpenAI with exponential backoff on 429 errors (up to 3 retries)."""
    max_retries = 3
    delays = [2, 4, 8]

    payload = {
        "model": chosen_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            req = request.Request(
                f"{base_url.rstrip('/')}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with request.urlopen(req, timeout=120) as response:
                raw_payload = json.loads(response.read().decode("utf-8"))
            return json.loads(_extract_text_from_chat_response(raw_payload))
        except HTTPError as e:
            last_error = e
            if e.code == 429 and attempt < max_retries:
                delay = delays[attempt - 1]
                print(
                    f"L3: OpenAI attempt {attempt}/{max_retries} failed (429). "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                if e.code == 429:
                    print(
                        f"L3: OpenAI attempt {attempt}/{max_retries} failed (429)."
                    )
                raise
        except Exception:
            raise

    # Should not be reached, but just in case
    raise last_error  # type: ignore[misc]


def _call_ollama(
    system_prompt: str,
    user_prompt: str,
) -> Dict[str, Any]:
    """Fallback to local Ollama server (OpenAI-compatible endpoint)."""
    ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "phi4-mini:latest")

    print(
        f"L3: All OpenAI retries exhausted. "
        f"Falling back to Ollama ({ollama_model})..."
    )

    # Ollama may not support response_format, so instruct via system prompt
    augmented_system = system_prompt + "\n\nYou must return ONLY valid JSON."

    payload = {
        "model": ollama_model,
        "messages": [
            {"role": "system", "content": augmented_system},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
    }

    req = request.Request(
        f"{ollama_base.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            # No Authorization header — Ollama doesn't need one
        },
        method="POST",
    )

    with request.urlopen(req, timeout=300) as response:
        raw_payload = json.loads(response.read().decode("utf-8"))

    raw_text = _extract_text_from_chat_response(raw_payload)

    try:
        return json.loads(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"L3: Ollama response was not valid JSON: {exc}")
        return {"raw_response": raw_text, "error": "ollama_json_parse_failed"}


def chat_json(
    system_prompt: str, user_prompt: str, model: str | None = None
) -> Dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    chosen_model = model or os.environ.get("OPENAI_MODEL", "gpt-5.1")

    # --- Try OpenAI first (with retries) ---
    if api_key:
        try:
            return _call_openai(base_url, api_key, chosen_model, system_prompt, user_prompt)
        except Exception as e:
            print(f"L3: OpenAI call failed: {e}")
    else:
        print("L3: OPENAI_API_KEY is not set. Skipping OpenAI, using Ollama.")

    # --- Fallback to Ollama ---
    return _call_ollama(system_prompt, user_prompt)
