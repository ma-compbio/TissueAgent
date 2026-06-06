"""REPL history compression (strategy 2H).

The coding and hypothesis sub-agents run an internal AI → Python →
AI → Python loop. Each iteration adds one AI message (containing an
``<execute>`` block) and one ``HumanMessage`` carrying the REPL stdout.
Long analyses can accumulate dozens of iterations, each potentially
several thousand tokens. Re-sending the full transcript on every loop
turn drives both context-window overflow and TPM exhaustion.

We keep the last *K* iterations in full and collapse all older
iterations into compact placeholder messages, preserving the first AI
message (the agent's initial plan, if any) and the most recent
``HumanMessage`` that triggered the current turn.

The compression is applied only to the list of messages we pass to the
LLM; the graph state itself is left untouched so the UI trace panel and
session exports retain the full history.
"""

from __future__ import annotations


from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


# Number of most-recent AI/Human REPL pairs to keep verbatim.
_KEEP_RECENT_PAIRS = 3

# Soft minimum: when there are this many or fewer total messages, do not
# bother compressing at all. Keeps short conversations untouched.
_MIN_MESSAGES_TO_COMPRESS = 8


def _content_len(msg: BaseMessage) -> int:
    c = msg.content
    if isinstance(c, str):
        return len(c)
    if isinstance(c, list):
        return sum(
            len(p.get("text", "")) if isinstance(p, dict) else len(str(p)) for p in c
        )
    return len(str(c))


def compress_repl_history(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Return *messages* with old REPL iterations collapsed.

    Heuristic: the loop alternates AI (with code) and Human (REPL output).
    We treat each consecutive (AI, Human) pair after the initial user
    prompt as one iteration, keep the last ``_KEEP_RECENT_PAIRS``
    iterations verbatim, and replace earlier iterations with a single
    summary line.

    The initial ``HumanMessage`` (the user's prompt that started the
    sub-agent invocation) is always preserved verbatim.
    """
    if len(messages) <= _MIN_MESSAGES_TO_COMPRESS:
        return messages

    # Find the boundary of the initial user prompt(s) — preserve everything
    # up to and including the last leading HumanMessage that precedes the
    # first AIMessage.
    first_ai_idx = next(
        (i for i, m in enumerate(messages) if isinstance(m, AIMessage)), None
    )
    if first_ai_idx is None:
        return messages
    preamble = messages[:first_ai_idx]
    body = messages[first_ai_idx:]

    # Walk the body and group into (AI, optional Human) pairs.
    pairs: list[list[BaseMessage]] = []
    i = 0
    while i < len(body):
        if isinstance(body[i], AIMessage):
            pair: list[BaseMessage] = [body[i]]
            if i + 1 < len(body) and isinstance(body[i + 1], HumanMessage):
                pair.append(body[i + 1])
                i += 2
            else:
                i += 1
            pairs.append(pair)
        else:
            # Stray non-AI message in the body — keep as its own "pair".
            pairs.append([body[i]])
            i += 1

    if len(pairs) <= _KEEP_RECENT_PAIRS + 1:
        return messages

    keep_pairs = pairs[-_KEEP_RECENT_PAIRS:]
    drop_pairs = pairs[:-_KEEP_RECENT_PAIRS]

    omitted_iters = len(drop_pairs)
    omitted_chars = sum(_content_len(m) for pair in drop_pairs for m in pair)

    placeholder = HumanMessage(
        content=(
            f"[earlier REPL history compressed: {omitted_iters} iteration(s) "
            f"and ~{omitted_chars} characters omitted to stay under the "
            f"context limit; the latest {_KEEP_RECENT_PAIRS} iteration(s) "
            f"are shown below in full]"
        )
    )

    compressed: list[BaseMessage] = []
    compressed.extend(preamble)
    compressed.append(placeholder)
    for pair in keep_pairs:
        compressed.extend(pair)
    return compressed
