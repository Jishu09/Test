import asyncio
import logging

from pyrogram import Client

from bot.config import Config, validate_config
from plugins import register_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logger = logging.getLogger("AutoCaptionBotPro")


async def start_health_server():
    """Tiny HTTP server so PaaS platforms (Render/Railway/Koyeb) see an open port."""
    try:
        from aiohttp import web

        async def health(_request):
            return web.Response(text="AutoCaptionBot Pro is running.")

        webapp = web.Application()
        webapp.router.add_get("/", health)
        webapp.router.add_get("/health", health)
        runner = web.AppRunner(webapp)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", Config.PORT)
        await site.start()
        logger.info(f"Health-check server listening on port {Config.PORT}")
    except Exception as e:
        logger.warning(f"Health server not started: {e}")


def main():
    validate_config()

    app = Client(
        name="AutoCaptionBotPro",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.BOT_TOKEN,
        in_memory=True,
    )

    register_all(app)

    async def runner():
        await start_health_server()
        await app.start()
        me = await app.get_me()
        app.bot_id = me.id
        app.bot_username = me.username
        logger.info(f"Bot started as @{me.username}")

        from utils.telegram_log_handler import attach as attach_error_log

        attach_error_log(app, Config.LOG_CHANNEL)

        if Config.LOG_CHANNEL:
            try:
                await app.send_message(
                    Config.LOG_CHANNEL,
                    f"✅ **{Config.BOT_NAME} started.**\n@{me.username} is now online.",
                )
            except Exception:
                pass
        await asyncio.Event().wait()

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(runner())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        try:
            from bot.caption_engine import close_tmdb_session

            loop.run_until_complete(close_tmdb_session())
        except Exception:
            pass


if __name__ == "__main__":
    main()
