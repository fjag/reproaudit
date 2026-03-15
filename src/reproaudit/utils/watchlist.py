"""Library watchlist for REPRO-005: packages with known behavioural changes across versions.

Each entry documents which version boundary is significant and why.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class WatchlistEntry:
    install_name: str
    import_name: str
    reason: str
    safe_pin: str  # recommended pin expression


WATCHLIST: List[WatchlistEntry] = [
    WatchlistEntry(
        "numpy", "numpy",
        "Random API changed in 1.17 (legacy RandomState vs Generator); dtype defaults changed in 1.24",
        "numpy>=1.24,<2.0",
    ),
    WatchlistEntry(
        "scikit-learn", "sklearn",
        "Estimator defaults changed in 0.24, 1.0, 1.1 (e.g. n_estimators, max_features, solver); "
        "pipeline behaviour changed across minor versions",
        "scikit-learn>=1.3,<2.0",
    ),
    WatchlistEntry(
        "torch", "torch",
        "Default generator behaviour, determinism APIs (torch.use_deterministic_algorithms) added in 1.8; "
        "various op defaults changed across 1.x and 2.x",
        "torch>=2.0,<3.0",
    ),
    WatchlistEntry(
        "tensorflow", "tensorflow",
        "Op non-determinism and random seed APIs changed significantly between 1.x and 2.x; "
        "default behaviours differ between 2.x minor versions",
        "tensorflow>=2.12,<3.0",
    ),
    WatchlistEntry(
        "pandas", "pandas",
        "Nullable dtypes introduced in 1.0; groupby sort default, copy-on-write semantics changed in 2.0; "
        "many silent behaviour changes between 1.x minor versions",
        "pandas>=2.0,<3.0",
    ),
    WatchlistEntry(
        "scipy", "scipy",
        "Random state propagation and several statistical function defaults changed across 1.x",
        "scipy>=1.10,<2.0",
    ),
    WatchlistEntry(
        "lifelines", "lifelines",
        "API changes in 0.27+; fitting and prediction interfaces changed",
        "lifelines>=0.27,<1.0",
    ),
    WatchlistEntry(
        "statsmodels", "statsmodels",
        "Default solver and convergence criteria changed across 0.13 and 0.14",
        "statsmodels>=0.14,<1.0",
    ),
]

WATCHLIST_BY_IMPORT: Dict[str, WatchlistEntry] = {e.import_name: e for e in WATCHLIST}
WATCHLIST_BY_INSTALL: Dict[str, WatchlistEntry] = {e.install_name: e for e in WATCHLIST}
