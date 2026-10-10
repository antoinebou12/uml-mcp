"""The circuit breaker that stops a hung Kroki engine from slowing every render."""

import threading

import pytest

from mcp_core.core.engine_health import EngineHealth, EngineUnavailable


class Clock:
    """Controllable time, so no test depends on real seconds passing."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make(cooldown: float = 60.0, threshold: int = 2) -> tuple[EngineHealth, Clock]:
    clock = Clock()
    return (
        EngineHealth(
            "Mermaid", cooldown=lambda: cooldown, threshold=threshold, clock=clock
        ),
        clock,
    )


def trip(health: EngineHealth, times: int = 2) -> None:
    for _ in range(times):
        health.failure()


def test_a_new_engine_is_not_open() -> None:
    health, _ = make()

    assert not health.is_open()
    assert health.retry_in() == 0


def test_one_failure_is_not_enough_two_are() -> None:
    health, _ = make()

    health.failure()
    assert not health.is_open()
    health.failure()
    assert health.is_open()
    assert health.retry_in() == 60


def test_it_closes_by_itself_after_the_cooldown() -> None:
    health, clock = make()
    trip(health)

    clock.advance(59)
    assert health.is_open()
    clock.advance(2)
    assert not health.is_open()


def test_a_failure_right_after_the_cooldown_reopens_immediately() -> None:
    """Half-open: the engine had its chance; one more failure means it is still down."""
    health, clock = make()
    trip(health)
    clock.advance(61)

    health.failure()

    assert health.is_open()


def test_a_success_after_the_cooldown_closes_it_for_good() -> None:
    health, clock = make()
    trip(health)
    clock.advance(61)

    health.success()
    health.failure()

    assert not health.is_open()  # back to counting from zero


def test_a_success_resets_the_failure_count() -> None:
    health, _ = make()

    health.failure()
    health.success()
    health.failure()

    assert not health.is_open()


def test_success_closes_an_open_breaker() -> None:
    health, _ = make()
    trip(health)

    health.success()

    assert not health.is_open()


def test_cooldown_zero_disables_everything() -> None:
    health, _ = make(cooldown=0)

    trip(health, times=5)

    assert not health.is_open()


def test_the_cooldown_is_read_at_call_time() -> None:
    """An admin changing the setting takes effect without a restart."""
    clock = Clock()
    cooldown = [60.0]
    health = EngineHealth("Mermaid", cooldown=lambda: cooldown[0], clock=clock)
    trip(health)
    assert health.is_open()

    cooldown[0] = 0

    assert not health.is_open()


def test_reset_forgets_everything() -> None:
    health, _ = make()
    trip(health)

    health.reset()

    assert not health.is_open()
    health.failure()
    assert not health.is_open()  # the count restarted too


def test_concurrent_failures_are_counted_safely() -> None:
    """Batch renders hit the breaker from several threads at once."""
    health, _ = make(threshold=40)

    threads = [threading.Thread(target=health.failure) for _ in range(40)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert health.is_open()  # exactly 40 failures were seen, none lost


def test_unavailable_error_reports_the_wait() -> None:
    err = EngineUnavailable("Mermaid", 42.4)

    assert err.engine == "Mermaid"
    assert "42s" in str(err)


@pytest.mark.parametrize("threshold", [1, 3])
def test_the_threshold_is_configurable(threshold: int) -> None:
    health, _ = make(threshold=threshold)

    for _ in range(threshold - 1):
        health.failure()
    assert not health.is_open()
    health.failure()
    assert health.is_open()
