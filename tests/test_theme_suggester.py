"""tests/test_theme_suggester.py — Sugestão de tema (fallback + sucesso mockado)."""

from __future__ import annotations

from config import settings
from modules import theme_suggester


def test_suggest_themes_cai_pro_fallback_sem_chave_openai(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    sugestoes = theme_suggester.suggest_themes(n=3)
    assert sugestoes == theme_suggester.SUGESTOES_FALLBACK[:3]


def test_suggest_themes_cai_pro_fallback_se_openai_falhar(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")

    class _ClienteQuebrado:
        def __init__(self, api_key=None):
            pass

        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise RuntimeError("API fora do ar")

    monkeypatch.setattr(theme_suggester, "OpenAI", _ClienteQuebrado)
    sugestoes = theme_suggester.suggest_themes(n=2)
    assert sugestoes == theme_suggester.SUGESTOES_FALLBACK[:2]


def test_suggest_themes_usa_resposta_da_openai_quando_disponivel(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")

    class _Resposta:
        class _Choice:
            class _Message:
                content = "Direito Médico — erro de diagnóstico\nDireito Trabalhista — home office"
            message = _Message()
        choices = [_Choice()]

    class _ClienteFalso:
        def __init__(self, api_key=None):
            pass

        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    return _Resposta()

    monkeypatch.setattr(theme_suggester, "OpenAI", _ClienteFalso)
    sugestoes = theme_suggester.suggest_themes(n=2)
    assert sugestoes == [
        "Direito Médico — erro de diagnóstico",
        "Direito Trabalhista — home office",
    ]
