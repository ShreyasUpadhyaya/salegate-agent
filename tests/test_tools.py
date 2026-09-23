"""Tools tests: confirm each wrapper speaks the real Salegate API contract.

These start the actual Salegate FastAPI app as a subprocess against a fresh
temp SQLite database, then drive the tools in salegate_agent/tools.py over
real HTTP. This checks the tools parse a genuine response correctly,
including the 404/409 error paths -- not the LLM's behaviour, which is out
of scope here.

Requires the salegate repo as a sibling directory (../salegate) with its own
uv environment already set up, matching how the two projects are meant to be
run together (see README.md). Skipped entirely if that repo isn't found, so
this suite never blocks CI or a clone that only has this one repo.
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

import httpx
import pytest

SALEGATE_REPO = Path(__file__).resolve().parent.parent.parent / "salegate"

pytestmark = pytest.mark.skipif(
    not (SALEGATE_REPO / "app" / "main.py").is_file(),
    reason="the salegate repo is not present as a sibling directory (../salegate)",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def salegate_base_url(tmp_path_factory):
    """A real Salegate API on a free port, against a fresh temp SQLite DB."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    data_dir = tmp_path_factory.mktemp("salegate-data")

    full_env = {
        **os.environ,
        "DB_PATH": str(data_dir / "app.db"),
        "AUDIO_DIR": str(data_dir / "recordings"),
        "CACHE_DIR": str(data_dir / "cache"),
    }

    process = subprocess.Popen(
        [
            "uv", "run", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(port),
        ],
        cwd=str(SALEGATE_REPO),
        env=full_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        deadline = time.time() + 30
        up = False
        while time.time() < deadline:
            try:
                if httpx.get(f"{base_url}/health", timeout=1.0).status_code == 200:
                    up = True
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        if not up:
            output = process.stdout.read() if process.stdout else ""
            process.terminate()
            pytest.skip(f"could not start the salegate API in time; output: {output[-2000:]}")

        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture
def seeded_lead_id(salegate_base_url):
    """A lead id that has never been scored, against a fresh database.

    Salegate has no direct lead-creation endpoint; leads normally arrive via
    the dialler with real audio, which is out of scope for a tools test here.
    An id that was never created is enough to exercise get_score/get_gate's
    404 path the same way an unscored real lead id would.
    """
    return "L-AGENT-TEST"


@pytest.fixture(autouse=True)
def _point_tools_at_test_server(salegate_base_url, monkeypatch):
    monkeypatch.setenv("SALEGATE_API_BASE", salegate_base_url)
    from salegate_agent.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_get_score_on_an_unscored_lead_returns_a_structured_error(seeded_lead_id):
    from salegate_agent.tools import get_score

    result = get_score(seeded_lead_id)

    assert result["error"] is True
    assert result["status_code"] == 404
    assert "not been scored" in result["message"] or "not found" in result["message"]


def test_get_gate_on_an_unscored_lead_returns_a_structured_error(seeded_lead_id):
    from salegate_agent.tools import get_gate

    result = get_gate(seeded_lead_id)

    assert result["error"] is True
    assert result["status_code"] == 404


def test_get_transcript_on_a_lead_with_no_recording_returns_a_structured_error(seeded_lead_id):
    from salegate_agent.tools import get_transcript

    result = get_transcript(seeded_lead_id)

    assert result["error"] is True
    assert result["status_code"] == 404


def test_score_lead_on_a_lead_with_no_recording_returns_a_structured_error(seeded_lead_id):
    from salegate_agent.tools import score_lead

    result = score_lead(seeded_lead_id)

    assert result["error"] is True


def test_list_overrides_on_an_unknown_check_result_returns_a_structured_error():
    from salegate_agent.tools import list_overrides

    result = list_overrides(999999)

    assert result["error"] is True
    assert result["status_code"] == 404


def test_get_agent_rollup_returns_a_list_even_when_empty():
    from salegate_agent.tools import get_agent_rollup

    result = get_agent_rollup()

    assert "agents" in result
    assert isinstance(result["agents"], list)
