import json

from conftest import FakeProvider

from evaluation.judge import LLMJudge, _resolve_judge
from triage.config import Settings
from triage.schemas import TriageInput, TriageOutput


def _settings(**over):
    base = dict(classifier_provider="anthropic", anthropic_api_key="a")
    base.update(over)
    return Settings(**base)


def test_auto_prefers_cross_family_openai():
    provider, model, key = _resolve_judge(_settings(openai_api_key="o"))
    assert provider == "openai"
    assert key == "o"


def test_auto_picks_gemini_when_only_google_key():
    provider, model, _ = _resolve_judge(_settings(google_api_key="g"))
    assert provider == "gemini"
    assert model == "gemini-2.5-flash"


def test_auto_falls_back_same_family_when_no_cross_family_key():
    provider, _, _ = _resolve_judge(_settings())  # only the anthropic classifier key
    assert provider == "anthropic"  # same family — warning is logged


def test_pinned_judge_provider_is_respected():
    provider, model, key = _resolve_judge(
        _settings(google_api_key="g", judge_provider="gemini", judge_model="gemini-1.5-pro")
    )
    assert provider == "gemini"
    assert model == "gemini-1.5-pro"


def test_evaluate_with_fake_provider():
    judge_json = json.dumps(
        {
            "scores": [
                {"field": f, "score": 4, "reasoning": "ok"}
                for f in (
                    "tipo_solicitacao",
                    "entidades",
                    "proxima_acao",
                    "confianca",
                    "justificativa",
                )
            ],
            "critical_errors": [],
            "judge_confidence": "alto",
        }
    )
    judge = LLMJudge(_settings(openai_api_key="o"), provider=FakeProvider(judge_json))
    output = TriageOutput(
        id=1,
        tipo_solicitacao="interesse_em_credito_pj",
        area_sugerida="comercial",
        proxima_acao="encaminhar_comercial",
        confianca="alto",
        urgencia="baixa",
        justificativa="Justificativa longa o suficiente para validar o schema corretamente.",
    )
    result = judge.evaluate(TriageInput(id=1, mensagem="crédito PJ"), output)
    assert result.overall_score == 4.0
    assert len(result.scores) == 5


def test_extract_json_object_with_surrounding_prose():
    from evaluation.judge import extract_json_object
    raw_text = (
        "Here is the reasoning:\n"
        "- The message was good.\n"
        "And the final JSON: \n"
        '{"scores": [{"field": "tipo_solicitacao", "score": 10, "reasoning": "excelente"}], "judge_confidence": "alto"}'
    )
    result = extract_json_object(raw_text, "scores")
    assert result is not None
    assert result["judge_confidence"] == "alto"
    assert len(result["scores"]) == 1


def test_extract_json_object_with_other_braces_in_prose():
    from evaluation.judge import extract_json_object
    raw_text = (
        "We choose {tipo_solicitacao} here.\n"
        '{"foo": "bar"}\n'
        "Final score JSON:\n"
        '{"scores": [{"field": "tipo_solicitacao", "score": 8, "reasoning": "ok"}], "judge_confidence": "medio"}'
    )
    result = extract_json_object(raw_text, "scores")
    assert result is not None
    assert result["judge_confidence"] == "medio"
    assert len(result["scores"]) == 1


def test_evaluate_retries_on_invalid_json():
    # Make sure LLMJudge retries if the provider returns invalid JSON first, then valid JSON.
    class FlakyProvider:
        def __init__(self):
            self.calls = 0
            self.model = "gpt-4o"
            self.name = "openai"

        def complete(self, system, messages, temperature, max_tokens):
            self.calls += 1
            if self.calls == 1:
                # Return invalid JSON
                return '{\n  "scores": [\n     {"field": "tipo_solicitacao"\n     "score": 10}\n  ]\n}'
            else:
                # Return valid JSON
                return json.dumps(
                    {
                        "scores": [
                            {"field": f, "score": 5, "reasoning": "ok"}
                            for f in (
                                "tipo_solicitacao",
                                "entidades",
                                "proxima_acao",
                                "confianca",
                                "justificativa",
                            )
                        ],
                        "critical_errors": [],
                        "judge_confidence": "medio",
                    }
                )

    provider = FlakyProvider()
    judge = LLMJudge(_settings(openai_api_key="o"), provider=provider)
    output = TriageOutput(
        id=1,
        tipo_solicitacao="interesse_em_credito_pj",
        area_sugerida="comercial",
        proxima_acao="encaminhar_comercial",
        confianca="alto",
        urgencia="baixa",
        justificativa="Justificativa longa o suficiente.",
    )
    result = judge.evaluate(TriageInput(id=1, mensagem="crédito PJ"), output)
    assert result.overall_score == 5.0
    assert provider.calls == 2
