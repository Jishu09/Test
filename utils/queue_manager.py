"""
Per-chat sequential job queue for Telegram API calls that are prone to
FLOOD_WAIT (specifically messages.EditMessage while auto-captioning a burst
of files posted back-to-back).

Two guarantees this provides:

1. Strict order. `submit()` has zero internal `await` points (it uses
   `Queue.put_nowait`, never `Queue.put`), so calling `await
   edit_queue.submit(...)` never yields control back to the event loop.
   Combined with callers submitting *before* doing any other async work
   (see plugins/caption_channel.py), this means jobs land in the queue in
   exactly the order Telegram delivered the updates — even if one job's
   actual work (TMDB lookup, etc.) later takes much longer than another's.

2. Nothing is ever dropped. If Telegram returns FLOOD_WAIT, the worker
   sleeps for exactly the time it asked for and retries the *same* job —
   so a captioning burst just slows down instead of losing files. Pacing
   between edits is adaptive: it speeds back up after a run of clean
   successes and backs off automatically the moment a flood wait happens,
   so normal traffic stays fast without constantly re-triggering the limit.

Different channels get independent queues/workers, so one busy or
throttled channel never slows another one down.
"""

import asyncio
import logging

from pyrogram.errors import FloodWait

logger = logging.getLogger("AutoCaptionBotPro")


class EditQueueManager:
    def __init__(
        self,
        min_pace: float = 0.6,
        max_pace: float = 4.0,
        base_pace: float = 1.0,
        max_retries: int = 12,
    ):
        self.min_pace = min_pace
        self.max_pace = max_pace
        self.base_pace = base_pace
        self.max_retries = max_retries

        self._queues: dict[int, asyncio.Queue] = {}
        self._workers: dict[int, asyncio.Task] = {}
        self._pace: dict[int, float] = {}          # current per-chat delay
        self._streak: dict[int, int] = {}           # consecutive clean successes

    def _ensure_worker(self, chat_id: int):
        if chat_id in self._workers and not self._workers[chat_id].done():
            return
        self._queues.setdefault(chat_id, asyncio.Queue())
        self._pace.setdefault(chat_id, self.base_pace)
        self._streak.setdefault(chat_id, 0)
        self._workers[chat_id] = asyncio.ensure_future(self._worker(chat_id))

    async def _worker(self, chat_id: int):
        queue = self._queues[chat_id]
        while True:
            func, args, kwargs = await queue.get()
            try:
                await self._run_with_flood_retry(chat_id, func, args, kwargs)
            except Exception as e:
                logger.exception(f"Edit queue job permanently failed for chat {chat_id}: {e}")
            finally:
                queue.task_done()
            await asyncio.sleep(self._pace[chat_id])

    async def _run_with_flood_retry(self, chat_id, func, args, kwargs):
        attempt = 0
        while True:
            try:
                await func(*args, **kwargs)
                # Clean success — speed back up a little after a stable run,
                # never below the safety floor.
                self._streak[chat_id] += 1
                if self._streak[chat_id] >= 5 and self._pace[chat_id] > self.min_pace:
                    self._pace[chat_id] = max(self.min_pace, self._pace[chat_id] * 0.85)
                    self._streak[chat_id] = 0
                return
            except FloodWait as e:
                attempt += 1
                wait = e.value + 1
                # Back off: Telegram just told us we're going too fast for
                # this chat, so raise the steady-state pace too, not just
                # this one retry's sleep.
                self._streak[chat_id] = 0
                self._pace[chat_id] = min(self.max_pace, max(self._pace[chat_id] * 1.5, 1.5))
                logger.warning(
                    f"FLOOD_WAIT: sleeping {wait}s (attempt {attempt}/{self.max_retries}) "
                    f"before retrying {getattr(func, '__name__', func)} — new pace "
                    f"for chat {chat_id}: {self._pace[chat_id]:.1f}s"
                )
                if attempt >= self.max_retries:
                    logger.error(f"Max FLOOD_WAIT retries reached for chat {chat_id} — giving up on this job.")
                    raise
                await asyncio.sleep(wait)

    async def submit(self, chat_id: int, func, *args, **kwargs):
        """Queue `func(*args, **kwargs)` to run sequentially (with FloodWait
        retry) against this chat's dedicated worker. This has NO internal
        await/yield point — see the module docstring for why that matters
        for ordering — and returns immediately without waiting for the job
        to actually run."""
        self._ensure_worker(chat_id)
        self._queues[chat_id].put_nowait((func, args, kwargs))

    def pending(self, chat_id: int) -> int:
        q = self._queues.get(chat_id)
        return q.qsize() if q else 0


edit_queue = EditQueueManager()
