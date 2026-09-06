from .encoder import SLatEncoder, ElasticSLatEncoder

_DECODER_MODULES = {
    'SLatGaussianDecoder': 'decoder_gs',
    'ElasticSLatGaussianDecoder': 'decoder_gs',
    'SLatRadianceFieldDecoder': 'decoder_rf',
    'ElasticSLatRadianceFieldDecoder': 'decoder_rf',
    'SLatMeshDecoder': 'decoder_mesh',
    'ElasticSLatMeshDecoder': 'decoder_mesh',
}

__all__ = ['SLatEncoder', 'ElasticSLatEncoder', *_DECODER_MODULES]


def __getattr__(name):
    if name not in _DECODER_MODULES:
        raise AttributeError(f'module {__name__} has no attribute {name}')

    import importlib

    module = importlib.import_module(f'.{_DECODER_MODULES[name]}', __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
