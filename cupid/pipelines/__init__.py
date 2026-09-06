import importlib


def __getattr__(name):
    if name == "samplers":
        value = importlib.import_module(".samplers", __name__)
    elif name == "Cupid3DPipeline":
        value = getattr(importlib.import_module(".pipeline", __name__), name)
    else:
        raise AttributeError(f"module {__name__} has no attribute {name}")
    globals()[name] = value
    return value


def from_pretrained(path: str):
    """
    Load a pipeline from a model folder or a Hugging Face model hub.

    Args:
        path: The path to the model. Can be either local path or a Hugging Face model name.
    """
    import os
    import json
    is_local = os.path.exists(f"{path}/pipeline.json")

    if is_local:
        config_file = f"{path}/pipeline.json"
    else:
        from huggingface_hub import hf_hub_download
        config_file = hf_hub_download(path, "pipeline.json")

    with open(config_file, 'r') as f:
        config = json.load(f)
    return __getattr__(config['name']).from_pretrained(path)
