import importlib

__attributes = {
    'SparseStructureEncoder': 'sparse_structure_vae',
    'SparseStructureDecoder': 'sparse_structure_vae',

    'SparseStructureFlowModel': 'sparse_structure_flow',
    'MultiPoseSparseStructureFlowModel': 'sparse_structure_flow',
    
    'SLatEncoder': 'structured_latent_vae',
    'SLatGaussianDecoder': 'structured_latent_vae',
    'SLatRadianceFieldDecoder': 'structured_latent_vae',
    'SLatMeshDecoder': 'structured_latent_vae',
    'ElasticSLatEncoder': 'structured_latent_vae',
    'ElasticSLatGaussianDecoder': 'structured_latent_vae',
    'ElasticSLatRadianceFieldDecoder': 'structured_latent_vae',
    'ElasticSLatMeshDecoder': 'structured_latent_vae',
    
    'SLatFlowModel': 'structured_latent_flow',
    'ElasticSLatFlowModel': 'structured_latent_flow',
    'LatentConditioningSLatFlowModel': 'structured_latent_flow',
    'ElasticLatentConditioningSLatFlowModel': 'structured_latent_flow',
    'MaskLatentConditioningSLatFlowModel': 'structured_latent_flow',
    'ElasticMaskLatentConditioningSLatFlowModel': 'structured_latent_flow',
    'VisualLatentConditioningSLatFlowModel': 'structured_latent_flow',
    'ElasticVisualLatentConditioningSLatFlowModel': 'structured_latent_flow',
    'PositionalEmbeddingConditioningSLatFlowModel': 'structured_latent_flow',
    'ElasticPositionalEmbeddingConditioningSLatFlowModel': 'structured_latent_flow',
    'SpatialConditioningSLatFlowModel': 'structured_latent_flow',
    'ElasticSpatialConditioningSLatFlowModel': 'structured_latent_flow',


}

__submodules = []

__all__ = list(__attributes.keys()) + __submodules

def __getattr__(name):
    if name not in globals():
        if name in __attributes:
            module_name = __attributes[name]
            module = importlib.import_module(f".{module_name}", __name__)
            globals()[name] = getattr(module, name)
        elif name in __submodules:
            module = importlib.import_module(f".{name}", __name__)
            globals()[name] = module
        else:
            raise AttributeError(f"module {__name__} has no attribute {name}")
    return globals()[name]


def from_pretrained(path: str, **kwargs):
    """
    Load a model from a pretrained checkpoint.

    Args:
        path: The path to the checkpoint. Can be either local path or a Hugging Face model name.
              NOTE: config file and model file should take the name f'{path}.json' and f'{path}.safetensors' respectively.
        **kwargs: Additional arguments for the model constructor.
    """
    import os
    import json
    from safetensors.torch import load_file
    is_local = os.path.exists(f"{path}.json") and os.path.exists(f"{path}.safetensors")

    if is_local:
        config_file = f"{path}.json"
        model_file = f"{path}.safetensors"
    else:
        from huggingface_hub import hf_hub_download
        path_parts = path.split('/')
        repo_id = f'{path_parts[0]}/{path_parts[1]}'
        model_name = '/'.join(path_parts[2:])
        config_file = hf_hub_download(repo_id, f"{model_name}.json")
        model_file = hf_hub_download(repo_id, f"{model_name}.safetensors")

    with open(config_file, 'r') as f:
        config = json.load(f)
    model_args = dict(config['args'])
    # Bind the official local SLAT encoder when an assembly omits the hub path.
    if config['name'] == 'ElasticVisualLatentConditioningSLatFlowModel' and 'pretrained_slat_enc' not in model_args:
        encoder_prefix = os.path.join(os.path.dirname(path), 'slat_enc_swin8_B_64l8_fp16')
        if os.path.exists(f'{encoder_prefix}.json') and os.path.exists(f'{encoder_prefix}.safetensors'):
            model_args['pretrained_slat_enc'] = encoder_prefix
    model = __getattr__(config['name'])(**model_args, **kwargs)
    model.load_state_dict(load_file(model_file))

    return model


# For Pylance
if __name__ == '__main__':
    from .sparse_structure_vae import (
        SparseStructureEncoder, 
        SparseStructureDecoder,
    )
    
    from .sparse_structure_flow import (
        SparseStructureFlowModel,
    )
    
    from .structured_latent_vae import (
        SLatEncoder,
        SLatGaussianDecoder,
        SLatRadianceFieldDecoder,
        SLatMeshDecoder,
        ElasticSLatEncoder,
        ElasticSLatGaussianDecoder,
        ElasticSLatRadianceFieldDecoder,
        ElasticSLatMeshDecoder,
    )
    
    from .structured_latent_flow import (
        SLatFlowModel,
        ElasticSLatFlowModel,
        LatentConditioningSLatFlowModel,
        ElasticLatentConditioningSLatFlowModel,
        VisualLatentConditioningSLatFlowModel,
        ElasticVisualLatentConditioningSLatFlowModel,
        PositionalEmbeddingConditioningSLatFlowModel,
        ElasticPositionalEmbeddingConditioningSLatFlowModel,
        SpatialConditioningSLatFlowModel,
        ElasticSpatialConditioningSLatFlowModel,
    )
