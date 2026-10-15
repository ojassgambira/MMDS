"""Identify hosted Colab from its runtime environment, including child processes."""
import os
from pathlib import Path


def is_colab() -> bool:
    return Path('/content').is_dir() and (
        bool(os.environ.get('COLAB_RELEASE_TAG') or os.environ.get('COLAB_BACKEND_VERSION'))
        or os.environ.get('MMDS_COLAB_RUNTIME') == '1')
