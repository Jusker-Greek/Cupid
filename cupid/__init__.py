import importlib


__all__ = ["models", "modules", "pipelines", "renderers", "representations", "utils"]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(f"module {__name__} has no attribute {name}")
    module = importlib.import_module(f".{name}", __name__)
    globals()[name] = module
    return module
