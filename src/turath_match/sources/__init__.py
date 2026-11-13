"""Source adapters. Each yields :class:`~turath_match.models.Record`; ``open_source("scheme:location")`` picks one."""

from . import archive, csvsrc, folder, openiti, shamela, waqfeya
from .archive import ArchiveDump, ArchiveOrg
from .base import JsonlSource, ListSource, Source, open_source, save_jsonl, schemes
from .csvsrc import CsvSource
from .folder import FolderSource, parse_name
from .openiti import OpenITI
from .shamela import ShamelaLocal
from .waqfeya import Waqfeya, WaqfeyaDump

__all__ = [
    "ArchiveDump",
    "ArchiveOrg",
    "CsvSource",
    "FolderSource",
    "JsonlSource",
    "ListSource",
    "OpenITI",
    "ShamelaLocal",
    "Source",
    "Waqfeya",
    "WaqfeyaDump",
    "archive",
    "csvsrc",
    "folder",
    "open_source",
    "openiti",
    "parse_name",
    "save_jsonl",
    "schemes",
    "shamela",
    "waqfeya",
]
