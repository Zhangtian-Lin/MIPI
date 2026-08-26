import json
import os

import pytest
from mipi.modules.collection.data_gov_my import DataGovMyConnector
from mipi.modules.collection.infrastructure import SafeHttpFetcher

pytestmark = pytest.mark.skipif(
    os.getenv("MIPI_RUN_NETWORK_INTEGRATION") != "1",
    reason="set MIPI_RUN_NETWORK_INTEGRATION=1 for the one-request official API probe",
)


def test_official_data_gov_my_connector_returns_one_trade_record() -> None:
    output = DataGovMyConnector(SafeHttpFetcher()).collect(
        "trade_sitc_1d", limit=1, task_id="network-sample-review"
    )

    assert output.record_count == 1
    assert output.byte_count < 2_000_000
    assert output.submission.raw_content is not None
    payload = json.loads(output.submission.raw_content)
    assert isinstance(payload, list)
    assert len(payload) == 1
