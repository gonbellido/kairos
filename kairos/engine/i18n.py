"""Fase E: Multilanguage engine — English + Spanish i18n."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SUPPORTED_LANGS = {"es", "en"}
DEFAULT_LANG = "es"

I18N_DIR = Path(__file__).parent.parent / "i18n"


class I18nEngine:
    """Loads and manages translations for UI and prompts."""

    def __init__(self, lang: str = DEFAULT_LANG):
        self._lang = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
        self._translations: dict[str, dict] = {}
        self._load(self._lang)

    def _load(self, lang: str):
        path = I18N_DIR / f"{lang}.json"
        if not path.exists():
            logger.warning("Translation file not found: %s", path)
            self._translations = {}
            return
        try:
            self._translations = json.loads(path.read_text(encoding="utf-8"))
            logger.debug("Loaded translations for '%s'", lang)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load translations for '%s': %s", lang, e)
            self._translations = {}

    def set_lang(self, lang: str):
        if lang != self._lang and lang in SUPPORTED_LANGS:
            self._lang = lang
            self._load(lang)

    @property
    def lang(self) -> str:
        return self._lang

    def t(self, key: str, default: str = "", **kwargs) -> str:
        """Translate a UI key. Falls back to key if not found."""
        parts = key.split(".")
        node = self._translations.get("ui", {})
        for part in parts:
            node = node.get(part, {}) if isinstance(node, dict) else node
        if isinstance(node, str):
            result = node
        elif isinstance(node, dict):
            result = default or key
        else:
            result = str(node) if node else default or key

        if kwargs:
            try:
                result = result.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return result

    def prompt(self, key: str, default: str = "") -> str:
        """Get a prompt translation."""
        parts = key.split(".")
        node = self._translations.get("prompts", {})
        for part in parts:
            node = node.get(part, {}) if isinstance(node, dict) else node
        return node if isinstance(node, str) else (default or key)

    def get_ui_dict(self) -> dict:
        """Return all UI translations as a flat dict for template injection."""
        return self._translations.get("ui", {})

    def detect_from_text(self, text: str) -> str:
        """Heuristic language detection from message text."""
        es_markers = [
            "hola", "gracias", "cómo", "qué", "por favor", "ayuda",
            "estoy", "necesito", "quiero", "puedo", "debo", "tengo",
            "buenos días", "buenas tardes", "buenas noches",
        ]
        en_markers = [
            "hello", "thanks", "how", "what", "please", "help",
            "I am", "I need", "I want", "I can", "I should", "I have",
            "good morning", "good afternoon", "good evening",
        ]
        text_lower = text.lower().strip()

        es_score = sum(1 for m in es_markers if m in text_lower)
        en_score = sum(1 for m in en_markers if m in text_lower)

        if es_score > en_score:
            return "es"
        if en_score > es_score:
            return "en"
        return self._lang


# Singleton
_i18n: I18nEngine | None = None


def get_i18n(lang: str | None = None) -> I18nEngine:
    global _i18n
    if _i18n is None:
        _i18n = I18nEngine(lang or DEFAULT_LANG)
    elif lang and lang in SUPPORTED_LANGS:
        _i18n.set_lang(lang)
    return _i18n


def detect_lang(message: str) -> str:
    """Detect message language for auto-switching."""
    return get_i18n().detect_from_text(message)
