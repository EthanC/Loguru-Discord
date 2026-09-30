import logging
import subprocess
import sys
from pathlib import Path
from threading import Thread
from unittest.mock import Mock

import pytest

from loguru_discord._delivery import delivery_active
from loguru_discord.intercept import Intercept


@pytest.mark.parametrize("mode", ["sync", "queued"])
@pytest.mark.parametrize("failure", ["none", "http", "transport"])
def test_transport_logs_do_not_feed_back(
    mode: str, failure: str, webhook_url: str
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.loguru_discord.transport_probe",
            mode,
            failure,
            webhook_url,
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_delivery_guard_is_local_to_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    forwarded = Mock()
    monkeypatch.setattr("loguru_discord.intercept.logger", forwarded)
    interceptor = Intercept(None)
    record = logging.LogRecord(
        "application", logging.INFO, __file__, 1, "Message", (), None
    )
    token = delivery_active.set(True)
    try:
        interceptor.emit(record)
        forwarded.opt.assert_not_called()
        thread = Thread(target=interceptor.emit, args=(record,))
        thread.start()
        thread.join(timeout=5)
        assert not thread.is_alive()
        forwarded.opt.return_value.log.assert_called_once()
        assert delivery_active.get()
    finally:
        delivery_active.reset(token)
    assert not delivery_active.get()
