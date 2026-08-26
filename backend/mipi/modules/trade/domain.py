import json
import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from typing import Any, Literal

FactLevel = Literal["F0", "F1", "F2", "F3", "F4"]
DetailedSITCSection = Literal["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
SITCSection = Literal["overall", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]

DATASET_ID = "trade_sitc_1d"
DETAILED_SITC_SECTIONS: tuple[DetailedSITCSection, ...] = (
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
)
SITC_SECTIONS: tuple[SITCSection, ...] = ("overall", *DETAILED_SITC_SECTIONS)

SITC_LABELS_ZH: dict[SITCSection, str] = {
    "overall": "全部商品",
    "0": "食品及活动物",
    "1": "饮料及烟草",
    "2": "非食用原料（燃料除外）",
    "3": "矿物燃料、润滑油及相关材料",
    "4": "动植物油、脂及蜡",
    "5": "化学品及相关产品",
    "6": "按原料分类的制成品",
    "7": "机械及运输设备",
    "8": "杂项制成品",
    "9": "其他未分类商品",
}


@dataclass(frozen=True)
class TradeObservation:
    period: date
    section: SITCSection
    exports_rm_million: Decimal
    imports_rm_million: Decimal

    @property
    def balance_rm_million(self) -> Decimal:
        return self.exports_rm_million - self.imports_rm_million


@dataclass(frozen=True)
class TradeBatch:
    public_id: str
    ingestion_id: str
    dataset_id: str
    status: str
    observation_count: int
    duplicate: bool


@dataclass(frozen=True)
class TradePublication:
    public_id: str
    batch_id: str
    revision: int
    projection: dict[str, object]
    duplicate: bool


class TradeIngestionNotFoundError(Exception):
    pass


class TradeIngestionNotApprovedError(Exception):
    pass


class TradeBatchNotFoundError(Exception):
    pass


class TradeProjectionConflictError(Exception):
    pass


class TradePublicationConflictError(Exception):
    pass


def normalize_trade_payload(raw_content: str) -> tuple[TradeObservation, ...]:
    try:
        payload: Any = json.loads(raw_content)
    except json.JSONDecodeError as error:
        raise ValueError("Trade input must be valid JSON") from error
    if not isinstance(payload, list) or not payload:
        raise ValueError("Trade input must be a non-empty JSON list")

    observations: list[TradeObservation] = []
    keys: set[tuple[date, SITCSection]] = set()
    for index, raw in enumerate(payload):
        if not isinstance(raw, dict):
            raise ValueError(f"Trade row {index} must be an object")
        period = _period(raw.get("date"), index)
        section = _section(raw.get("section"), index)
        key = (period, section)
        if key in keys:
            raise ValueError(f"Trade row {index} duplicates {period.isoformat()} / {section}")
        keys.add(key)
        observations.append(
            TradeObservation(
                period=period,
                section=section,
                exports_rm_million=_amount(raw.get("exports"), "exports", index),
                imports_rm_million=_amount(raw.get("imports"), "imports", index),
            )
        )
    return tuple(sorted(observations, key=lambda item: (item.period, item.section)))


def build_trade_overview(
    observations: tuple[TradeObservation, ...],
    *,
    evidence: dict[str, object],
) -> dict[str, object]:
    overall = sorted(
        (item for item in observations if item.section == "overall"),
        key=lambda item: item.period,
    )
    if len(overall) < 12:
        raise ValueError("Publication requires at least 12 monthly overall observations")
    if any(
        _next_month(previous.period) != current.period
        for previous, current in pairwise(overall[-12:])
    ):
        raise ValueError("Publication requires 12 consecutive monthly overall observations")
    latest = overall[-1]
    latest_sections: dict[DetailedSITCSection, TradeObservation] = {
        item.section: item
        for item in observations
        if item.period == latest.period and item.section != "overall"
    }
    missing = [section for section in DETAILED_SITC_SECTIONS if section not in latest_sections]
    if missing:
        raise ValueError(
            "Publication requires a complete latest SITC month; missing sections: "
            + ", ".join(missing)
        )
    previous = overall[-2]
    return {
        "dataset_id": DATASET_ID,
        "title": "马来西亚月度货物贸易（SITC 一位数）",
        "unit": "RM million",
        "latest_period": latest.period.isoformat(),
        "provisional_periods": [item.period.isoformat() for item in overall[-2:]],
        "latest": _metric_payload(latest, previous),
        "timeline": [
            {
                "period": item.period.isoformat(),
                "exports_rm_million": _number(item.exports_rm_million),
                "imports_rm_million": _number(item.imports_rm_million),
                "balance_rm_million": _number(item.balance_rm_million),
                "provisional": item in overall[-2:],
            }
            for item in overall[-12:]
        ],
        "sections": [
            {
                "section": section,
                "label_zh": SITC_LABELS_ZH[section],
                "exports_rm_million": _number(latest_sections[section].exports_rm_million),
                "imports_rm_million": _number(latest_sections[section].imports_rm_million),
                "balance_rm_million": _number(latest_sections[section].balance_rm_million),
            }
            for section in DETAILED_SITC_SECTIONS
        ],
        "fact_level": "F4",
        "caveats": ["最近两个月数据为暂定值，后续更新可能修订。"],
        "evidence": evidence,
    }


def _metric_payload(current: TradeObservation, previous: TradeObservation) -> dict[str, object]:
    return {
        "exports_rm_million": _number(current.exports_rm_million),
        "imports_rm_million": _number(current.imports_rm_million),
        "balance_rm_million": _number(current.balance_rm_million),
        "exports_mom_percent": _percent_change(
            current.exports_rm_million, previous.exports_rm_million
        ),
        "imports_mom_percent": _percent_change(
            current.imports_rm_million, previous.imports_rm_million
        ),
    }


def _period(value: object, index: int) -> date:
    if not isinstance(value, str):
        raise ValueError(f"Trade row {index} date must be a string")
    try:
        result = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"Trade row {index} date must use YYYY-MM-DD") from error
    if result.day != 1:
        raise ValueError(f"Trade row {index} date must be the first day of a month")
    return result


def _section(value: object, index: int) -> SITCSection:
    if not isinstance(value, str) or value not in SITC_SECTIONS:
        raise ValueError(f"Trade row {index} has an unsupported SITC section")
    return value


def _amount(value: object, field: str, index: int) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError(f"Trade row {index} {field} must be numeric")
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"Trade row {index} {field} must be numeric") from error
    if not result.is_finite() or result < 0:
        raise ValueError(f"Trade row {index} {field} must be finite and non-negative")
    return result


def _number(value: Decimal) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Trade value is outside the supported numeric range")
    return result


def _percent_change(current: Decimal, previous: Decimal) -> float | None:
    if previous == 0:
        return None
    return round(float((current - previous) / previous * 100), 2)


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)
