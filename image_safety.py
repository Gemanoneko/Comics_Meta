"""Disable Pillow's external EPS/Ghostscript decoder at engine startup."""
from PIL import Image, EpsImagePlugin


def _disabled(*args, **kwargs):
    raise OSError('EPS decoding is disabled')


def install():
    Image.init()
    Image.OPEN.pop('EPS', None)
    Image.ID[:] = [name for name in Image.ID if name != 'EPS']
    EpsImagePlugin.Ghostscript = _disabled
    EpsImagePlugin.has_ghostscript = lambda: False


install()
