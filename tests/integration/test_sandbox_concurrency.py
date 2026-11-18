"""Opt-in parallel HTTP checks against the separately launched synthetic sandbox only."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SANDBOX_HTTP_TESTS") != "1",
    reason="Requires isolated sandbox API on 127.0.0.1:8001",
)


def test_concurrent_analysis_and_case_linking_are_consistent():
    with httpx.Client(
        base_url="http://127.0.0.1:8001/api/v1/intelligence",
        headers={"X-FraudSentinel-Sandbox": "synthetic-only"},
        timeout=20,
    ) as client:
        capability = client.get("/capabilities").json()
        assert capability["enabled"] and capability["mode"] == "synthetic_sandbox"
        prefix = "parallel_" + uuid4().hex[:16]
        for suffix in ("a", "b"):
            assert (
                client.post(
                    "/accounts",
                    json={
                        "account_id": f"{prefix}_{suffix}",
                        "data_source": "concurrent_synthetic_fixture",
                        "is_synthetic": True,
                    },
                ).status_code
                == 201
            )
        assert (
            client.post(
                "/transactions",
                json={
                    "transaction_id": prefix,
                    "source_account_id": f"{prefix}_a",
                    "destination_account_id": f"{prefix}_b",
                    "amount": "10.00",
                    "currency": "INR",
                    "occurred_at": "2026-11-18T12:00:00Z",
                    "transaction_type": "transfer",
                    "status": "completed",
                    "data_source": "concurrent_synthetic_fixture",
                    "is_synthetic": True,
                },
            ).status_code
            == 201
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(lambda _: client.post(f"/transactions/{prefix}/analyze"), range(2))
            )
        assert [r.status_code for r in results] == [200, 200]
        assert (
            results[0].json()["assessment"]["assessment_id"]
            == results[1].json()["assessment"]["assessment_id"]
        )
        case_ids = [f"{prefix}_case_a", f"{prefix}_case_b"]
        for identifier in case_ids:
            assert (
                client.post(
                    "/cases", json={"case_id": identifier, "title": "Concurrent synthetic review"}
                ).status_code
                == 201
            )
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda identifier: client.post(
                        f"/cases/{identifier}/links", json={"transaction_ids": [prefix]}
                    ),
                    case_ids,
                )
            )
        assert sorted(r.status_code for r in results) == [200, 409]
        winner = next(r.json()["case_id"] for r in results if r.status_code == 200)
        assert client.get(f"/transactions/{prefix}").json()["transaction"]["case_id"] == winner
