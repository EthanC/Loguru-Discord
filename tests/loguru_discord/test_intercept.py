import inspect
import logging
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from threading import Thread
from typing import Any
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
        encoding="utf-8",
        errors="replace",
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


@pytest.mark.parametrize("named", [False, True])
@pytest.mark.parametrize("application_filter", [False, True])
def test_intercept_caller(
    named: bool, application_filter: bool, add_sink: Callable[..., int]
) -> None:
    records: list[dict[str, Any]] = []

    def capture(message: Any) -> None:
        records.append(message.record)

    add_sink(capture, filter=__name__ if application_filter else None)
    Intercept.setup()
    source = logging.getLogger(__name__) if named else logging

    frame = inspect.currentframe()
    assert frame is not None
    line = frame.f_lineno + 1
    source.warning("Application %s", "record")

    assert len(records) == 1
    record = records[0]
    assert record["name"] == __name__
    assert record["module"] == "test_intercept"
    assert record["function"] == "test_intercept_caller"
    assert record["file"].name == Path(__file__).name
    assert Path(record["file"].path).resolve() == Path(__file__).resolve()
    assert record["line"] == line
    assert record["message"] == "Application record"


def test_intercept_without_caller_frame(
    add_sink: Callable[..., int], monkeypatch: pytest.MonkeyPatch
) -> None:
    records: list[dict[str, Any]] = []

    def capture(message: Any) -> None:
        records.append(message.record)

    add_sink(capture)
    monkeypatch.setattr("loguru_discord.intercept.logging.currentframe", lambda: None)
    record = logging.LogRecord(
        __name__, logging.WARNING, __file__, 1, "Application %s", ("record",), None
    )

    Intercept(None).emit(record)

    assert len(records) == 1
    assert records[0]["message"] == "Application record"
    assert records[0]["level"].name == "WARNING"
    assert records[0]["level"].no == logging.WARNING
    assert records[0]["exception"] is None


@pytest.mark.parametrize("named", [False, True])
def test_intercept_preserves_exception(
    named: bool, add_sink: Callable[..., int]
) -> None:
    records: list[dict[str, Any]] = []
    formatted: list[str] = []

    def capture(message: Any) -> None:
        records.append(message.record)
        formatted.append(str(message))

    add_sink(capture, filter=__name__)
    Intercept.setup()
    source = logging.getLogger(__name__) if named else logging
    error = ValueError("Invalid application value")

    try:
        raise error
    except ValueError:
        source.exception("Application failure")

    assert len(records) == 1
    exception = records[0]["exception"]
    assert exception.type is ValueError
    assert exception.value is error
    assert exception.traceback is error.__traceback__
    assert "Traceback (most recent call last):" in formatted[0]
    assert "ValueError: Invalid application value" in formatted[0]


@pytest.mark.parametrize(
    ("level_name", "level_no", "level_map", "expected_name", "expected_no"),
    [
        ("WARNING", 30, {"WARNING": "ERROR", "ERROR": "CRITICAL"}, "ERROR", 40),
        ("WARNING", 30, {"ERROR": "CRITICAL", "WARNING": "ERROR"}, "ERROR", 40),
        ("WARNING", 30, {}, "WARNING", 30),
        ("INFO", 20, None, "INFO", 20),
        ("ERROR", 40, {"WARNING": "CRITICAL"}, "ERROR", 40),
        ("NOTICE", 35, {"NOTICE": "SUCCESS"}, "SUCCESS", 25),
        ("SUCCESS", 25, None, "SUCCESS", 25),
        ("NOTICE", 35, None, "Level 35", 35),
        ("NOTICE", 35, {"NOTICE": "UNREGISTERED"}, "Level 35", 35),
    ],
)
def test_level_mapping_preserves_original_record(
    level_name: str,
    level_no: int,
    level_map: dict[str, str] | None,
    expected_name: str,
    expected_no: int,
    add_sink: Callable[..., int],
) -> None:
    forwarded: list[dict[str, Any]] = []
    observed: list[dict[str, Any]] = []

    def capture(message: Any) -> None:
        forwarded.append(message.record)

    class Observer(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            observed.append(record.__dict__.copy())

    add_sink(capture, level="TRACE")
    Intercept.setup(level_map)
    root = logging.getLogger()
    root.addHandler(Observer())
    record = logging.LogRecord(
        __name__, level_no, __file__, 1, "Application %s", ("record",), None
    )
    record.levelname = level_name
    original = record.__dict__.copy()

    root.handle(record)

    assert len(forwarded) == 1
    assert forwarded[0]["message"] == "Application record"
    assert forwarded[0]["level"].name == expected_name
    assert forwarded[0]["level"].no == expected_no
    assert observed == [original]
    assert record.__dict__ == original
