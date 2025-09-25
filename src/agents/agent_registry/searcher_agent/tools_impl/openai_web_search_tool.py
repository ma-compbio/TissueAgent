# agents/web_search_agent/tools_impl/openai_web_search_tool.py
from __future__ import annotations
from typing import Optional, Any, List
from dataclasses import dataclass

from openai import OpenAI
from openai import APIConnectionError, RateLimitError, OpenAIError


def _coerce_secret(v: Any) -> str:
    return v.get_secret_value() if hasattr(v, "get_secret_value") else v

def _extract_text(output: Any) -> str:
    if not output:
        return ""
    parts: List[str] = []
    for item in output:
        t = getattr(item, "type", None)
        if t == "message":
            for c in getattr(item, "content", []) or []:
                if getattr(c, "type", None) == "output_text":
                    txt = getattr(c, "text", None)
                    val = txt if isinstance(txt, str) else getattr(txt, "value", "")
                    if isinstance(val, str) and val.strip():
                        parts.append(val.strip())
        elif t == "output_text":
            txt = getattr(item, "text", None)
            if isinstance(txt, str) and txt.strip():
                parts.append(txt.strip())
            else:
                val = getattr(txt, "value", None)
                if isinstance(val, str) and val.strip():
                    parts.append(val.strip())
    return "\n\n".join(parts)

@dataclass
class OpenAIWebSearchEngine:
    api_key: Any
    default_model: str = "gpt-4o"

    def __post_init__(self):
        key = _coerce_secret(self.api_key)
        if not key or str(key).startswith("*"):
            raise ValueError("Invalid OpenAI API key")
        self.client = OpenAI(api_key=key)

    def run(
        self,
        query: str,
        model: Optional[str] = None,
        max_output_tokens: int = 2000,
        instructions: Optional[str] = None,
    ) -> str:
        q = (query or "").strip()
        if not q:
            return "Error: empty query."


        mdl = model or self.default_model
        sys = (
            "You are a web research tool. Search the web and produce a concise answer with live URLs. "
            "Prefer official/primary sources; include the canonical link first. If ambiguous, list the top 2 options."
        )
        if instructions:
            sys += " " + instructions.strip()

        try:
            resp = self.client.responses.create(
                model=mdl,
                instructions=sys,
                input=q,
                tools=[{"type": "web_search"}],
                max_output_tokens=max_output_tokens,
                parallel_tool_calls = False,
            )
 
            # Fast path
            txt = getattr(resp, "output_text", None)
            if isinstance(txt, str) and txt.strip():
                return txt.strip()
    
            # Fallback parse across shapes
            txt2 = _extract_text(getattr(resp, "output", None))
            return txt2 if txt2 else "No output from web search."

        except RateLimitError as e:
            return f"OpenAI web search rate-limited: {e}"
        except APIConnectionError as e:
            return f"OpenAI web search connection error: {e}"
        except OpenAIError as e:
            return f"OpenAI web search error: {e}"
        except Exception as e:
            return f"Unexpected error during OpenAI web search: {e}"
