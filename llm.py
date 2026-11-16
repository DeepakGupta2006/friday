"""The brain: streams tokens from a local Ollama model."""
import ollama

import config

_client = ollama.Client(host=config.OLLAMA_HOST)
_OPTIONS = {
    "num_predict": config.MAX_REPLY_TOKENS,
    "temperature": config.TEMPERATURE,
    "num_ctx": config.CONTEXT_TOKENS,
}


def warm_up():
    """Load the model into memory now so the first real answer is not slow."""
    _client.chat(
        model=config.LLM_MODEL,
        messages=[{"role": "user", "content": "hi"}],
        options={"num_predict": 1, "num_ctx": config.CONTEXT_TOKENS},
        keep_alive="30m",
    )


def stream_reply(messages):
    stream = _client.chat(
        model=config.LLM_MODEL,
        messages=messages,
        stream=True,
        options=_OPTIONS,
        keep_alive="30m",
    )
    for chunk in stream:
        text = chunk["message"]["content"]
        if text:
            yield text


def sentence_chunks(buffer: str):
    """Split streamed text into (finished sentences, leftover) so speech can start early."""
    done, start = [], 0
    for i, ch in enumerate(buffer):
        if ch in ".!?;:\n" and i - start >= 12:  
            done.append(buffer[start:i + 1].strip())
            start = i + 1
    return done, buffer[start:]
