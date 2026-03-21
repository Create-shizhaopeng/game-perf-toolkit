"""EventBus 单元测试"""

from __future__ import annotations

from toolkit.core.event_bus import EventBus


class TestEventBus:
    def test_on_and_emit(self) -> None:
        bus = EventBus()
        results = []
        bus.on("test.event", lambda **kw: results.append(kw))
        bus.emit("test.event", value=42)
        assert results == [{"value": 42}]

    def test_multiple_listeners(self) -> None:
        bus = EventBus()
        log: list[str] = []
        bus.on("evt", lambda **_: log.append("a"))
        bus.on("evt", lambda **_: log.append("b"))
        bus.emit("evt")
        assert log == ["a", "b"]

    def test_off_removes_listener(self) -> None:
        bus = EventBus()
        calls = []
        cb = lambda **_: calls.append(1)
        bus.on("evt", cb)
        bus.off("evt", cb)
        bus.emit("evt")
        assert calls == []

    def test_off_nonexistent_no_error(self) -> None:
        bus = EventBus()
        bus.off("no_event", lambda: None)

    def test_emit_unregistered_event(self) -> None:
        bus = EventBus()
        bus.emit("nonexistent")

    def test_listener_exception_does_not_stop_others(self) -> None:
        bus = EventBus()
        results = []

        def bad(**_):
            raise ValueError("boom")

        bus.on("evt", bad)
        bus.on("evt", lambda **_: results.append("ok"))
        bus.emit("evt")
        assert results == ["ok"]

    def test_list_events(self) -> None:
        bus = EventBus()
        bus.on("a", lambda **_: None)
        bus.on("a", lambda **_: None)
        bus.on("b", lambda **_: None)
        events = bus.list_events()
        assert events == {"a": 2, "b": 1}

    def test_clear(self) -> None:
        bus = EventBus()
        bus.on("a", lambda **_: None)
        bus.clear()
        assert bus.list_events() == {}

    def test_emit_with_kwargs(self) -> None:
        bus = EventBus()
        received = {}
        bus.on("data", lambda **kw: received.update(kw))
        bus.emit("data", device="abc", status="connected")
        assert received == {"device": "abc", "status": "connected"}
