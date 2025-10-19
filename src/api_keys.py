from pydantic import SecretStr
from typing_extensions import TypedDict

class APIKeys(TypedDict):
    llm: SecretStr
    openai: SecretStr
    serp: SecretStr
    email: str
