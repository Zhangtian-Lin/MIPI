# Integration tests

The first end-to-end integration target is:

```text
Ingestion envelope → document version → claim/evidence → review task → API projection
```

No real network collection is permitted in the default test suite.

The `data.gov.my` connector has a separate, one-request network sample review. Run it only while
the official API remains approved for trial evaluation and respect its 4 requests/minute limit:

```powershell
$env:MIPI_RUN_NETWORK_INTEGRATION='1'
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_data_gov_my_network.py
```

Environments that resolve public hosts to synthetic loopback/proxy addresses will be rejected by
the SSRF guard. Do not disable the guard to make this optional test pass; run it from an approved
direct-network CI runner instead.
