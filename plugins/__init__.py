import importlib
import pkgutil

PLUGIN_ORDER = [
    "guard",
    "fsub",
    "start",
    "lang",
    "settings",
    "channel_manager",
    "caption_channel",
    "broadcast",
    "admin",
]


def register_all(app):
    for name in PLUGIN_ORDER:
        module = importlib.import_module(f"plugins.{name}")
        module.register(app)

    # Pick up any additional plugin modules not explicitly listed above.
    known = set(PLUGIN_ORDER)
    pkg = importlib.import_module("plugins")
    for _, mod_name, _ in pkgutil.iter_modules(pkg.__path__):
        if mod_name not in known and mod_name != "__init__":
            module = importlib.import_module(f"plugins.{mod_name}")
            if hasattr(module, "register"):
                module.register(app)
