"""
Async Task Utilities - Sichere Task-Erstellung mit Error-Handling

Dieses Modul bietet Hilfsfunktionen fuer das sichere Erstellen von
Background-Tasks mit automatischem Exception-Handling und Logging.

Verwendung:
    from app.utils.async_tasks import create_safe_task

    # Statt: asyncio.create_task(my_coroutine())
    create_safe_task(my_coroutine(), name="my_task")
"""
import asyncio
import logging
from typing import Coroutine, Any, Optional, Callable

logger = logging.getLogger(__name__)


def _default_exception_handler(task: asyncio.Task) -> None:
    """
    Standard Exception-Handler fuer Tasks.

    Wird aufgerufen wenn ein Task mit Exception beendet wird.
    Logged die Exception statt sie stillschweigend zu verlieren.
    """
    try:
        task.result()
    except asyncio.CancelledError:
        # Task wurde abgebrochen - das ist OK
        task_name = task.get_name() if hasattr(task, 'get_name') else "unknown"
        logger.debug(f"Task '{task_name}' wurde abgebrochen")
    except Exception as exc:
        task_name = task.get_name() if hasattr(task, 'get_name') else "unknown"
        logger.exception(f"Unbehandelte Exception in Task '{task_name}': {exc}")


def create_safe_task(
    coro: Coroutine[Any, Any, Any],
    name: Optional[str] = None,
    exception_handler: Optional[Callable[[asyncio.Task], None]] = None,
) -> asyncio.Task:
    """
    Erstellt einen asyncio Task mit automatischem Exception-Handling.

    Diese Funktion ist ein sicherer Ersatz fuer asyncio.create_task().
    Sie sorgt dafuer, dass Exceptions in Background-Tasks nicht verloren gehen.

    Args:
        coro: Die Coroutine die ausgefuehrt werden soll
        name: Optionaler Name fuer den Task (fuer Logging)
        exception_handler: Optionaler Custom-Handler fuer Exceptions

    Returns:
        Der erstellte Task

    Beispiel:
        # Einfache Verwendung
        create_safe_task(send_notification(), name="notification")

        # Mit Custom-Handler
        def my_handler(task):
            error = task.exception()
            if error:
                notify_admin(f"Task failed: {error}")

        create_safe_task(important_work(), name="important", exception_handler=my_handler)
    """
    task = asyncio.create_task(coro, name=name)

    handler = exception_handler or _default_exception_handler
    task.add_done_callback(handler)

    return task


async def run_with_timeout(
    coro: Coroutine[Any, Any, Any],
    timeout_seconds: float,
    timeout_message: Optional[str] = None,
) -> Any:
    """
    Fuehrt eine Coroutine mit Timeout aus.

    Args:
        coro: Die auszufuehrende Coroutine
        timeout_seconds: Timeout in Sekunden
        timeout_message: Optionale Nachricht fuer TimeoutError

    Returns:
        Das Ergebnis der Coroutine

    Raises:
        asyncio.TimeoutError: Wenn der Timeout ueberschritten wird
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        msg = timeout_message or f"Operation timed out after {timeout_seconds}s"
        logger.warning(msg)
        raise asyncio.TimeoutError(msg)


class TaskGroup:
    """
    Einfache Task-Gruppe fuer das Verwalten mehrerer Background-Tasks.

    Verwendung:
        group = TaskGroup("my_service")
        group.add(some_coroutine(), "task1")
        group.add(other_coroutine(), "task2")
        await group.cancel_all()
    """

    def __init__(self, name: str):
        self.name = name
        self.tasks: list[asyncio.Task] = []

    def add(
        self,
        coro: Coroutine[Any, Any, Any],
        task_name: Optional[str] = None,
    ) -> asyncio.Task:
        """Fuegt einen neuen Task zur Gruppe hinzu"""
        full_name = f"{self.name}.{task_name}" if task_name else self.name
        task = create_safe_task(coro, name=full_name)
        self.tasks.append(task)
        return task

    async def cancel_all(self, timeout: float = 5.0) -> None:
        """Bricht alle Tasks ab und wartet auf Beendigung"""
        for task in self.tasks:
            if not task.done():
                task.cancel()

        if self.tasks:
            await asyncio.wait(self.tasks, timeout=timeout)
            logger.debug(f"TaskGroup '{self.name}': {len(self.tasks)} Tasks beendet")

        self.tasks.clear()

    @property
    def active_count(self) -> int:
        """Anzahl der noch laufenden Tasks"""
        return sum(1 for t in self.tasks if not t.done())
