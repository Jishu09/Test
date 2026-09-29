import asyncio

from pyrogram import Client, ContinuePropagation
from pyrogram import filters as pyrogram_filters
from pyrogram.handlers import MessageHandler


async def listen(self, chat_id, filters=None, timeout=None):
    future = asyncio.get_event_loop().create_future()

    def check_chat(flt, client, message):
        return message.chat and message.chat.id == flt.chat_id

    custom_filter = pyrogram_filters.create(check_chat, chat_id=chat_id)

    if filters is not None:
        final_filter = custom_filter & filters
    else:
        final_filter = custom_filter

    async def handler(client, message):
        if not future.done():
            future.set_result(message)
            raise ContinuePropagation

    handler_obj = MessageHandler(handler, filters=final_filter)
    self.add_handler(handler_obj, group=-1)

    try:
        if timeout is not None:
            return await asyncio.wait_for(future, timeout=timeout)
        else:
            return await future
    except asyncio.TimeoutError:
        return None
    finally:
        self.remove_handler(handler_obj, group=-1)


Client.listen = listen
