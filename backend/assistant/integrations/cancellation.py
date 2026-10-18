"""Cancel the outstanding HTTP task when the durable command is stopped."""
import asyncio
from contextlib import suppress
from .errors import RequestCancelled


def cancellable_request(factory, cancelled):
    async def wait():
        if await asyncio.to_thread(cancelled):
            raise RequestCancelled("Command cancelled.")
        task = asyncio.create_task(factory())
        try:
            while not task.done():
                await asyncio.wait({task}, timeout=0.25)
                if await asyncio.to_thread(cancelled):
                    raise RequestCancelled("Command cancelled.")
            return task.result()
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            elif not task.cancelled():
                # Consume a provider error that raced a cancellation, keeping
                # raw provider exception bodies out of unhandled-task logs.
                task.exception()
    return asyncio.run(wait())
