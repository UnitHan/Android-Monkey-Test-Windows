"""Shared fixtures. API tests use `api` (ContractClient); on failure, API logs are attached to the report."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from contract import ContractClient
from fakes import FakeAdb, healthy_device
from fastapi.testclient import TestClient

from monkey_api.adapters.ai.advisor import NoAdvisor
from monkey_api.core.logging import LogStore
from monkey_api.core.settings import Settings
from monkey_api.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        adb_path="adb-fake",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        log_level="WARNING",
        app_launch_wait_s=0,
        perf_interval_s=0.02,
        guard_interval_s=0.02,
        gemini_api_key=None,
        play_oauth_file=tmp_path / "play-oauth.json",
        play_packages=["com.lguplus.aicallagent"],
    )


@pytest.fixture
def adb() -> FakeAdb:
    return healthy_device()


@pytest.fixture
def log_store() -> LogStore:
    return LogStore(capacity=50_000)


@pytest.fixture
def api(
    settings: Settings, adb: FakeAdb, log_store: LogStore, request: pytest.FixtureRequest
) -> Iterator[ContractClient]:
    app = create_app(settings, adb=adb, log_store=log_store, advisor=NoAdvisor())
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as client:
        contract = ContractClient(client, log_store)
        request.node.contract_client = contract
        yield contract


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):  # type: ignore[no-untyped-def]
    report = yield
    contract: ContractClient | None = getattr(item, "contract_client", None)
    if contract is not None and report.failed and call.when == "call":
        report.sections.append(("API logs for this test's requests", contract.logs_for_requests() or "(none)"))
        report.sections.append(("API WARNING+ logs (incl. background sessions)", contract.problem_logs() or "(none)"))
    return report
