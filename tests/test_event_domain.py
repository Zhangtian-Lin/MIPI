from datetime import date

import pytest
from mipi.modules.events.domain import EventProjectionInput, validate_event_input


def make_input(**overrides: object) -> EventProjectionInput:
    values: dict[str, object] = {
        "ingestion_id": "ING-test",
        "event_type": "project_update",
        "title_zh": "柔佛项目宣布进入建设阶段",
        "summary_zh": "该摘要只陈述来源明确支持的项目阶段变化，并保留精确原文证据。",
        "event_date": date(2026, 8, 26),
        "event_date_precision": "day",
        "industries": ("data_centres_ai",),
        "states": ("johor",),
        "span_start": 6,
        "span_end": 18,
        "quote_original": "construction",
        "quote_zh": "进入建设阶段",
        "model_id": "test-model",
        "prompt_version": "event-v1",
        "conflict": False,
    }
    values.update(overrides)
    return EventProjectionInput(**values)  # type: ignore[arg-type]


def test_event_source_span_must_match_preserved_original() -> None:
    validate_event_input(make_input(), "Start construction announced")

    with pytest.raises(ValueError, match="does not match"):
        validate_event_input(
            make_input(quote_original="constructed!"), "Start construction announced"
        )


def test_event_projection_requires_product_scopes() -> None:
    with pytest.raises(ValueError, match="industry and state"):
        validate_event_input(make_input(states=()), "Start construction announced")
