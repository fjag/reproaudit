"""Maps Python import names to PyPI install names (and vice versa).

Many packages expose a different name at import time vs install time.
"""
from __future__ import annotations

# import_name -> install_name
IMPORT_TO_INSTALL: dict[str, str] = {
    "sklearn": "scikit-learn",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "ruamel": "ruamel.yaml",
    "dotenv": "python-dotenv",
    "gi": "PyGObject",
    "usearch": "usearch",
    "Bio": "biopython",
    "pysam": "pysam",
    "anndata": "anndata",
    "scanpy": "scanpy",
    "lifelines": "lifelines",
    "skbio": "scikit-bio",
    "umap": "umap-learn",
    "hdbscan": "hdbscan",
    "statsmodels": "statsmodels",
    "scipy": "scipy",
    "matplotlib": "matplotlib",
    "seaborn": "seaborn",
    "plotly": "plotly",
    "lightgbm": "lightgbm",
    "xgboost": "xgboost",
    "catboost": "catboost",
    "shap": "shap",
    "transformers": "transformers",
    "datasets": "datasets",
    "tokenizers": "tokenizers",
    "accelerate": "accelerate",
    "peft": "peft",
    "wandb": "wandb",
    "mlflow": "mlflow",
    "optuna": "optuna",
}

# install_name -> import_name (inverse, auto-built)
INSTALL_TO_IMPORT: dict[str, str] = {v: k for k, v in IMPORT_TO_INSTALL.items()}


def import_to_install(import_name: str) -> str:
    """Return the PyPI install name for a given import name."""
    return IMPORT_TO_INSTALL.get(import_name, import_name)


def install_to_import(install_name: str) -> str:
    """Return the import name for a given PyPI install name."""
    return INSTALL_TO_IMPORT.get(install_name, install_name)
