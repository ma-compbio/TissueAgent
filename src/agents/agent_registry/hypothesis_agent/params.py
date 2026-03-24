"""Model and parameter configuration for the hypothesis agent."""
from functools import partial
from langchain_openai import ChatOpenAI

# Model constructor configuration
model_ctor = partial(ChatOpenAI, model="gpt-5", reasoning_effort="high")
