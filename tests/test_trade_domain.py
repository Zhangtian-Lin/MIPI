import json
from datetime import date

import pytest
from mipi.modules.trade.domain import (
    build_trade_overview,
    normalize_trade_payload,
    trade_publication_blockers,
)
from mipi.modules.verification.domain import fact_level_for_official_trade_dataset


def test_normalize_trade_payload_preserves_month_section_and_amounts() -> None:
    observations = normalize_trade_payload(
        json.dumps(
            [
                {"date": "2026-05-01", "section": "overall", "exports": 12.5, "imports": 10},
                {"date": "2026-05-01", "section": "7", "exports": "7.25", "imports": 6},
            ]
        )
    )

    assert observations[0].period == date(2026, 5, 1)
    assert observations[0].section == "7"
    assert observations[0].balance_rm_million == 1.25
    assert observations[1].section == "overall"


@pytest.mark.parametrize(
    "row",
    [
        {"date": "2026-05-02", "section": "overall", "exports": 1, "imports": 1},
        {"date": "2026-05-01", "section": "10", "exports": 1, "imports": 1},
        {"date": "2026-05-01", "section": "0", "exports": -1, "imports": 1},
        {"date": "2026-05-01", "section": "0", "exports": True, "imports": 1},
    ],
)
def test_normalize_trade_payload_rejects_invalid_official_fields(row: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        normalize_trade_payload(json.dumps([row]))


def test_build_trade_overview_requires_complete_latest_month() -> None:
    rows = [
        {
            "date": f"2025-{month:02d}-01",
            "section": "overall",
            "exports": 100 + month,
            "imports": 90 + month,
        }
        for month in range(1, 13)
    ]
    with pytest.raises(ValueError, match="complete latest SITC month"):
        build_trade_overview(
            normalize_trade_payload(json.dumps(rows)), evidence={"source_id": "SRC-TEST"}
        )


def test_trade_readiness_reports_independent_timeline_and_section_blockers() -> None:
    observations = normalize_trade_payload(
        json.dumps(
            [
                {
                    "date": "2025-12-01",
                    "section": "overall",
                    "exports": 112,
                    "imports": 102,
                }
            ]
        )
    )

    blockers = trade_publication_blockers(observations)

    assert any("at least 12" in blocker for blocker in blockers)
    assert any("missing sections" in blocker for blocker in blockers)


def test_build_trade_overview_rejects_a_gap_in_the_public_timeline() -> None:
    rows = [
        {
            "date": f"2025-{month:02d}-01",
            "section": "overall",
            "exports": 100 + month,
            "imports": 90 + month,
        }
        for month in range(1, 13)
        if month != 6
    ]
    rows.append({"date": "2026-01-01", "section": "overall", "exports": 113, "imports": 103})
    for section in range(10):
        rows.append(
            {
                "date": "2026-01-01",
                "section": str(section),
                "exports": 10 + section,
                "imports": 8 + section,
            }
        )
    with pytest.raises(ValueError, match="consecutive"):
        build_trade_overview(
            normalize_trade_payload(json.dumps(rows)), evidence={"source_id": "SRC-TEST"}
        )


def test_build_trade_overview_marks_two_latest_months_provisional() -> None:
    rows: list[dict[str, object]] = []
    for month in range(1, 13):
        rows.append(
            {
                "date": f"2025-{month:02d}-01",
                "section": "overall",
                "exports": 100 + month,
                "imports": 90 + month,
            }
        )
    for section in range(10):
        rows.append(
            {
                "date": "2025-12-01",
                "section": str(section),
                "exports": 10 + section,
                "imports": 8 + section,
            }
        )

    overview = build_trade_overview(
        normalize_trade_payload(json.dumps(rows)), evidence={"source_id": "SRC-TEST"}
    )

    assert overview["latest_period"] == "2025-12-01"
    assert overview["provisional_periods"] == ["2025-11-01", "2025-12-01"]
    assert len(overview["timeline"]) == 12
    assert len(overview["sections"]) == 10
    assert overview["fact_level"] == "F4"


def test_official_trade_rule_requires_exact_reviewed_source_contract() -> None:
    assert (
        fact_level_for_official_trade_dataset(
            source_id="SRC-MY-DATAGOV",
            source_grade="S2",
            dataset_id="trade_sitc_1d",
            ingestion_status="approved",
            verification_hint="F4",
        )
        == "F4"
    )
    with pytest.raises(ValueError):
        fact_level_for_official_trade_dataset(
            source_id="SRC-OTHER",
            source_grade="S2",
            dataset_id="trade_sitc_1d",
            ingestion_status="approved",
            verification_hint="F4",
        )
