"""Single place for LLM provider creation.

Goal: users should switch providers by editing `.env`, not by changing many
Python files.
"""

from __future__ import annotations

import importlib
import os

import httpx
import config as runtime_config

from config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    GEMINI_MODEL,
    GOOGLE_API_KEY,
    GROQ_API_KEY,
    GROQ_MODEL,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_RETRIES,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_TIMEOUT_SECONDS,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    TOGETHER_API_KEY,
    TOGETHER_MODEL,
)


def _require(value: str, env_name: str, provider: str) -> str:
    if not value:
        raise ValueError(f"{provider} selected but {env_name} is missing in .env")
    return value


def _cfg():
    return importlib.reload(runtime_config)


def _no_proxy_http_client(timeout: int | float):
    return httpx.Client(timeout=timeout, trust_env=False)


def get_model_name() -> str:
    """Return selected model name from one generic setting or provider default."""
    cfg = _cfg()
    if cfg.LLM_MODEL:
        return cfg.LLM_MODEL
    defaults = {
        "openai": cfg.OPENAI_MODEL,
        "gemini": cfg.GEMINI_MODEL,
        "anthropic": cfg.ANTHROPIC_MODEL,
        "groq": cfg.GROQ_MODEL,
        "openrouter": cfg.OPENROUTER_MODEL,
        "together": cfg.TOGETHER_MODEL,
        "ollama": cfg.OLLAMA_MODEL,
        "custom": cfg.LLM_MODEL,
    }
    return defaults.get(cfg.LLM_PROVIDER, cfg.OPENAI_MODEL)


def get_llm(temperature: float = 0):
    """Create the configured chat model.

    Change only `.env`:
      LLM_PROVIDER=gemini/openai/anthropic/groq/openrouter/together/ollama/custom
      LLM_MODEL=optional_model_name
    """
    cfg = _cfg()
    provider = cfg.LLM_PROVIDER
    model = get_model_name()

    if provider == "gemini":
        _require(cfg.GOOGLE_API_KEY, "GOOGLE_API_KEY", "Gemini")
        # langchain-google-genai reads GOOGLE_API_KEY from env in most setups.
        os.environ["GOOGLE_API_KEY"] = cfg.GOOGLE_API_KEY
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            timeout=cfg.LLM_TIMEOUT_SECONDS,
            max_retries=cfg.LLM_MAX_RETRIES,
        )

    if provider == "openai":
        _require(cfg.OPENAI_API_KEY, "OPENAI_API_KEY", "OpenAI")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=cfg.OPENAI_API_KEY,
            temperature=temperature,
            timeout=cfg.LLM_TIMEOUT_SECONDS,
            max_retries=cfg.LLM_MAX_RETRIES,
            http_client=_no_proxy_http_client(cfg.LLM_TIMEOUT_SECONDS),
        )

    if provider == "anthropic":
        _require(cfg.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY", "Anthropic")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=cfg.ANTHROPIC_API_KEY,
            temperature=temperature,
            timeout=cfg.LLM_TIMEOUT_SECONDS,
            max_retries=cfg.LLM_MAX_RETRIES,
        )

    if provider == "groq":
        _require(cfg.GROQ_API_KEY, "GROQ_API_KEY", "Groq")
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=model,
            api_key=cfg.GROQ_API_KEY,
            temperature=temperature,
            timeout=cfg.LLM_TIMEOUT_SECONDS,
            max_retries=cfg.LLM_MAX_RETRIES,
            http_client=_no_proxy_http_client(cfg.LLM_TIMEOUT_SECONDS),
        )

    if provider == "openrouter":
        _require(cfg.OPENROUTER_API_KEY, "OPENROUTER_API_KEY", "OpenRouter")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=cfg.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=temperature,
            timeout=cfg.LLM_TIMEOUT_SECONDS,
            max_retries=cfg.LLM_MAX_RETRIES,
            http_client=_no_proxy_http_client(cfg.LLM_TIMEOUT_SECONDS),
        )

    if provider == "together":
        _require(cfg.TOGETHER_API_KEY, "TOGETHER_API_KEY", "Together AI")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=cfg.TOGETHER_API_KEY,
            base_url="https://api.together.xyz/v1",
            temperature=temperature,
            timeout=cfg.LLM_TIMEOUT_SECONDS,
            max_retries=cfg.LLM_MAX_RETRIES,
            http_client=_no_proxy_http_client(cfg.LLM_TIMEOUT_SECONDS),
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=model, base_url=cfg.OLLAMA_BASE_URL, temperature=temperature)

    if provider == "custom":
        _require(cfg.LLM_BASE_URL, "LLM_BASE_URL", "custom OpenAI-compatible provider")
        _require(cfg.LLM_API_KEY, "LLM_API_KEY", "custom OpenAI-compatible provider")
        if not model:
            raise ValueError("custom provider selected but LLM_MODEL is missing in .env")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=cfg.LLM_API_KEY,
            base_url=cfg.LLM_BASE_URL,
            temperature=temperature,
            timeout=cfg.LLM_TIMEOUT_SECONDS,
            max_retries=cfg.LLM_MAX_RETRIES,
            http_client=_no_proxy_http_client(cfg.LLM_TIMEOUT_SECONDS),
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER={provider}. Use one of: "
        "openai, gemini, anthropic, groq, openrouter, together, ollama, custom."
    )
