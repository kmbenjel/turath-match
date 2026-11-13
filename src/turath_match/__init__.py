"""turath-match: reconcile an Arabic heritage library with Shamela, Waqfeya, archive.org, OpenITI and your own CSV.

Every match carries its evidence and a confidence; uncertain matches go to a review list instead of being guessed.
"""

__version__ = "0.1.0"

from .dups import DuplicateGroup, find_duplicates, fingerprint
from .edition import match_edition
from .models import Evidence, FileRef, Match, Record
from .provenance import SizeIndex, trace
from .reconcile import Reconciliation, reconcile
from .work import match_work

__all__ = [
    "DuplicateGroup",
    "Evidence",
    "FileRef",
    "Match",
    "Reconciliation",
    "Record",
    "SizeIndex",
    "__version__",
    "find_duplicates",
    "fingerprint",
    "match_edition",
    "match_work",
    "reconcile",
    "trace",
]
