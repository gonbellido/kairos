import logging
from langchain_openai import ChatOpenAI
from kairos.config import get_settings

logger = logging.getLogger(__name__)


def create_llm(model: str | None = None, temperature: float | None = None, **kwargs) -> ChatOpenAI:
    """Crea el LLM principal (worker). Soporta OpenAI, DeepSeek, Anthropic (via openai-compat)."""
    settings = get_settings()
    provider = (settings.llm_provider or "openai").lower()

    params = {
        "model": model or settings.llm_model,
        "temperature": temperature if temperature is not None else settings.llm_temperature,
        "max_tokens": kwargs.pop("max_tokens", settings.llm_max_tokens),
        "api_key": settings.llm_api_key,
    }

    if settings.llm_base_url:
        params["base_url"] = settings.llm_base_url
    elif provider == "deepseek":
        params["base_url"] = "https://api.deepseek.com"

    params.update(kwargs)

    # Anthropic via OpenAI-compatible proxy
    if provider == "anthropic":
        # LangChain's ChatAnthropic is separate; use ChatOpenAI with Anthropic gateway
        params["default_headers"] = params.get("default_headers", {})
        params["default_headers"]["anthropic-version"] = "2023-06-01"

    logger.debug(
        "create_llm: provider=%s model=%s temp=%.2f",
        provider, params["model"], params["temperature"],
    )
    return ChatOpenAI(**params)


def create_eval_llm(**kwargs) -> ChatOpenAI:
    """Crea el LLM evaluador (validator, analyst) con modelo distinto al worker (D2)."""
    settings = get_settings()
    provider = (settings.llm_provider or "openai").lower()

    # D2: El evaluador puede usar un modelo más potente que el worker
    work_model = settings.llm_model
    eval_model = settings.evaluator_model

    if eval_model == work_model:
        logger.info(
            "EVALUATOR_MODEL es igual a LLM_MODEL (%s). Para multi-modelo, "
            "configura EVALUATOR_MODEL con un modelo distinto (ej: gpt-4o, claude-sonnet).",
            eval_model,
        )

    return create_llm(
        model=eval_model,
        temperature=0.0,
        **kwargs,
    )
