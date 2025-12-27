"""
Tests fuer das async_tasks Utility-Modul
"""
import asyncio
import pytest
from unittest.mock import MagicMock, patch

from app.utils.async_tasks import (
    create_safe_task,
    run_with_timeout,
    TaskGroup,
    _default_exception_handler,
)


# =============================================================================
# Helper Coroutines fuer Tests
# =============================================================================

async def successful_coro():
    """Coroutine die erfolgreich beendet wird"""
    await asyncio.sleep(0.01)
    return "success"


async def failing_coro():
    """Coroutine die eine Exception wirft"""
    await asyncio.sleep(0.01)
    raise ValueError("Test error")


async def slow_coro(delay: float = 1.0):
    """Langsame Coroutine fuer Timeout-Tests"""
    await asyncio.sleep(delay)
    return "completed"


async def cancellable_coro():
    """Coroutine die abgebrochen werden kann"""
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        raise


# =============================================================================
# Tests fuer create_safe_task
# =============================================================================

class TestCreateSafeTask:
    """Tests fuer die create_safe_task Funktion"""

    @pytest.mark.asyncio
    async def test_successful_task(self):
        """Test dass erfolgreiche Tasks normal funktionieren"""
        task = create_safe_task(successful_coro(), name="test_success")

        result = await task
        assert result == "success"

    @pytest.mark.asyncio
    async def test_task_with_name(self):
        """Test dass Task-Name gesetzt wird"""
        task = create_safe_task(successful_coro(), name="my_task_name")

        assert task.get_name() == "my_task_name"
        await task

    @pytest.mark.asyncio
    async def test_failing_task_logs_exception(self):
        """Test dass Exceptions geloggt werden"""
        with patch("app.utils.async_tasks.logger") as mock_logger:
            task = create_safe_task(failing_coro(), name="test_fail")

            # Task ausfuehren lassen
            await asyncio.sleep(0.05)

            # Exception Handler sollte aufgerufen worden sein
            assert mock_logger.exception.called

    @pytest.mark.asyncio
    async def test_custom_exception_handler(self):
        """Test dass Custom-Handler aufgerufen wird"""
        handler_called = False
        received_task = None

        def custom_handler(task):
            nonlocal handler_called, received_task
            handler_called = True
            received_task = task

        task = create_safe_task(
            successful_coro(),
            name="test_custom",
            exception_handler=custom_handler,
        )

        await task

        assert handler_called is True
        assert received_task == task

    @pytest.mark.asyncio
    async def test_cancelled_task_handled_gracefully(self):
        """Test dass abgebrochene Tasks nicht als Fehler geloggt werden"""
        with patch("app.utils.async_tasks.logger") as mock_logger:
            task = create_safe_task(cancellable_coro(), name="test_cancel")

            await asyncio.sleep(0.01)
            task.cancel()

            await asyncio.sleep(0.01)

            # Exception sollte NICHT geloggt werden (nur debug fuer cancel)
            assert not mock_logger.exception.called


# =============================================================================
# Tests fuer _default_exception_handler
# =============================================================================

class TestDefaultExceptionHandler:
    """Tests fuer den Standard Exception-Handler"""

    @pytest.mark.asyncio
    async def test_handler_logs_exception(self):
        """Test dass Exceptions geloggt werden"""
        task = asyncio.create_task(failing_coro())

        with patch("app.utils.async_tasks.logger") as mock_logger:
            await asyncio.sleep(0.05)
            _default_exception_handler(task)

            mock_logger.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_handler_handles_cancelled(self):
        """Test dass CancelledError speziell behandelt wird"""
        task = asyncio.create_task(cancellable_coro())
        task.cancel()

        with patch("app.utils.async_tasks.logger") as mock_logger:
            await asyncio.sleep(0.01)
            _default_exception_handler(task)

            # Sollte debug, nicht exception aufrufen
            mock_logger.debug.assert_called()
            assert not mock_logger.exception.called


# =============================================================================
# Tests fuer run_with_timeout
# =============================================================================

class TestRunWithTimeout:
    """Tests fuer die run_with_timeout Funktion"""

    @pytest.mark.asyncio
    async def test_successful_within_timeout(self):
        """Test dass schnelle Coroutine erfolgreich ist"""
        result = await run_with_timeout(successful_coro(), timeout_seconds=5.0)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_timeout_raises_error(self):
        """Test dass Timeout TimeoutError wirft"""
        with pytest.raises(asyncio.TimeoutError):
            await run_with_timeout(slow_coro(10.0), timeout_seconds=0.05)

    @pytest.mark.asyncio
    async def test_timeout_with_custom_message(self):
        """Test dass Custom-Message in TimeoutError enthalten ist"""
        with pytest.raises(asyncio.TimeoutError) as exc_info:
            await run_with_timeout(
                slow_coro(10.0),
                timeout_seconds=0.05,
                timeout_message="Custom timeout message",
            )

        assert "Custom timeout message" in str(exc_info.value)


# =============================================================================
# Tests fuer TaskGroup
# =============================================================================

class TestTaskGroup:
    """Tests fuer die TaskGroup Klasse"""

    @pytest.mark.asyncio
    async def test_add_task(self):
        """Test dass Tasks hinzugefuegt werden"""
        group = TaskGroup("test_group")
        task = group.add(successful_coro(), "task1")

        assert len(group.tasks) == 1
        assert task in group.tasks

    @pytest.mark.asyncio
    async def test_task_name_includes_group(self):
        """Test dass Task-Name Gruppenname enthaelt"""
        group = TaskGroup("my_group")
        task = group.add(successful_coro(), "my_task")

        assert task.get_name() == "my_group.my_task"
        await task

    @pytest.mark.asyncio
    async def test_active_count(self):
        """Test der active_count Property"""
        group = TaskGroup("test")
        group.add(slow_coro(10.0), "slow1")
        group.add(slow_coro(10.0), "slow2")

        await asyncio.sleep(0.01)
        assert group.active_count == 2

        await group.cancel_all()
        assert group.active_count == 0

    @pytest.mark.asyncio
    async def test_cancel_all(self):
        """Test dass alle Tasks abgebrochen werden"""
        group = TaskGroup("test")
        task1 = group.add(slow_coro(10.0), "slow1")
        task2 = group.add(slow_coro(10.0), "slow2")

        await asyncio.sleep(0.01)
        await group.cancel_all()

        assert task1.cancelled() or task1.done()
        assert task2.cancelled() or task2.done()
        assert len(group.tasks) == 0

    @pytest.mark.asyncio
    async def test_multiple_adds(self):
        """Test mehrfaches Hinzufuegen von Tasks"""
        group = TaskGroup("test")

        for i in range(5):
            group.add(successful_coro(), f"task{i}")

        assert len(group.tasks) == 5
        await group.cancel_all()


# =============================================================================
# Integration Tests
# =============================================================================

class TestAsyncTasksIntegration:
    """Integrationstests fuer async_tasks"""

    @pytest.mark.asyncio
    async def test_task_group_with_mixed_tasks(self):
        """Test TaskGroup mit erfolgreichen und fehlenden Tasks"""
        group = TaskGroup("mixed")

        # Ein erfolgreicher Task
        group.add(successful_coro(), "success")

        # Ein langsamer Task der abgebrochen wird
        group.add(slow_coro(10.0), "slow")

        await asyncio.sleep(0.05)

        # Erster Task sollte fertig sein
        assert group.tasks[0].done()

        # Alle abbrechen
        await group.cancel_all()

    @pytest.mark.asyncio
    async def test_create_safe_task_returns_task(self):
        """Test dass create_safe_task einen asyncio.Task zurueckgibt"""
        task = create_safe_task(successful_coro())

        assert isinstance(task, asyncio.Task)
        await task
