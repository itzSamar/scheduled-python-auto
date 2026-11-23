"""
Local LLM client (Ollama). Used for story triage, screenplay writing and safety second opinions.

Docs: https://github.com/ollama/ollama/blob/main/docs/api.md (structured outputs via `format`).
"""
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

import requests

from .config import OLLAMA_FAST_MODEL, OLLAMA_HOST, OLLAMA_MODEL

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> Dict[str, Any]:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", t)
        if not m:
            raise
        return json.loads(m.group(0))


class OllamaClient:
    def __init__(self, host: str = OLLAMA_HOST, model: str = OLLAMA_MODEL, fast_model: str = OLLAMA_FAST_MODEL):
        self.host = host.rstrip("/")
        self.model = model
        self.fast_model = fast_model or model

    # ----------------------------
    # Server / models
    # ----------------------------
    def available(self, timeout: float = 2.0) -> bool:
        try:
            return requests.get(f"{self.host}/api/version", timeout=timeout).status_code == 200
        except requests.RequestException:
            return False

    def ensure_server(self, wait_seconds: int = 45) -> bool:
        """Start Ollama if it isn't running (menu-bar app on macOS, else `ollama serve`)."""
        if self.available():
            return True
        if sys.platform == "darwin" and os.path.isdir("/Applications/Ollama.app"):
            subprocess.run(["open", "-g", "-a", "Ollama"], capture_output=True)
        else:
            exe = shutil.which("ollama")
            if not exe:
                return False
            subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if self.available():
                return True
            time.sleep(1.5)
        return False

    def models(self) -> List[str]:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=5)
            r.raise_for_status()
            return [m.get("name") for m in (r.json() or {}).get("models") or [] if m.get("name")]
        except requests.RequestException:
            return []

    def has_model(self, name: str) -> bool:
        names = set(self.models())
        return name in names or f"{name}:latest" in names

    def ready(self) -> bool:
        return self.ensure_server() and self.has_model(self.model)

    def unload(self, model: Optional[str] = None) -> None:
        """Free the model's memory (e.g. before a render)."""
        try:
            requests.post(f"{self.host}/api/generate", json={"model": model or self.model, "keep_alive": 0}, timeout=30)
        except requests.RequestException:
            pass

    # ----------------------------
    # Chat
    # ----------------------------
    def chat(self, messages: List[Dict[str, str]], *, model: Optional[str] = None, temperature: float = 0.7,
             think: Optional[bool] = None, fmt: Any = None, num_ctx: int = 16384, num_predict: int = 8192,
             timeout: int = 1200) -> str:
        body: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "temperature": float(temperature),
                "num_ctx": int(num_ctx),
                "num_predict": int(num_predict),
                "top_p": 0.95,
                "repeat_penalty": 1.05,
            },
        }
        if think is not None:
            body["think"] = bool(think)
        if fmt is not None:
            body["format"] = fmt
        last: Optional[Exception] = None
        for attempt in range(3):
            try:
                r = requests.post(f"{self.host}/api/chat", json=body, timeout=timeout)
                if r.status_code == 200:
                    msg = (r.json() or {}).get("message") or {}
                    return str(msg.get("content") or "")
                last = LLMError(f"Ollama chat failed: {r.status_code} {r.text[:300]}")
                if r.status_code == 404:
                    break
            except requests.RequestException as e:
                last = e
            time.sleep(3 * (attempt + 1))
        raise LLMError(str(last))

    def chat_json(self, schema: Dict[str, Any], messages: List[Dict[str, str]], *, schema_name: str = "result",
                  temperature: float = 0.7, model: Optional[str] = None, think: Optional[bool] = False,
                  num_predict: int = 8192) -> Dict[str, Any]:
        """Chat constrained to a JSON schema; returns the parsed object."""
        for attempt in range(2):
            content = self.chat(messages, model=model, temperature=temperature, think=think, fmt=schema,
                                num_predict=num_predict)
            try:
                data = _extract_json(content)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError as e:
                logger.warning(f"{schema_name}: model returned invalid JSON ({e}); retrying")
        raise LLMError(f"{schema_name}: no valid JSON from {model or self.model}")
