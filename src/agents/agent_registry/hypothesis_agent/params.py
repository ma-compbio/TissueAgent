"""Model and parameter configuration for the hypothesis agent."""
from models import model_ctor_for_role

# Hypothesis agent is a worker sub-agent; resolves the worker model at call time.
model_ctor = model_ctor_for_role("worker")
