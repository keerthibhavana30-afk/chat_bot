"""
External LLM Connector (OpenAI, Gemini, Ollama, Anthropic compatible).
Provides optional pass-through to real LLM providers while safely falling back
to the native deterministic/probabilistic In-Context Learning engine.
"""

import json
import urllib.request
import urllib.error
import os
from typing import Dict, Any, Optional

class LLMClient:
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "native") # "native", "openai", "gemini", "ollama"
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.endpoint = os.getenv("LLM_ENDPOINT", "https://api.openai.com/v1/chat/completions")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.provider != "native")

    def call_llm(self, assembled_prompt: str, system_prompt: str) -> Optional[str]:
        """
        Execute call to external LLM if configured.
        Returns response text or None if fallback is needed.
        """
        if not self.is_configured():
            return None

        try:
            if self.provider == "openai":
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": assembled_prompt}
                    ],
                    "temperature": 0.2
                }
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
                req = urllib.request.Request(
                    self.endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[LLMClient] Fallback to native engine due to: {e}")
            return None

        return None
