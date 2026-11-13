"""The records every source adapter yields, and the match results with their evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

#: verdicts of a comparison
SAME, RELATED, DIFFERENT, UNCERTAIN = "same", "related", "different", "uncertain"
#: what a reconciler does with it
MATCH, REVIEW, NO_MATCH = "match", "review", "no_match"
#: how the match was made (names shared with turath-catalog's ext_ids import)
EXACT_SIZE, HASH, SAMPLED_BYTES = "exact_size", "hash", "sampled_bytes"
EXACT_TITLE_AUTHOR, FUZZY_TITLE_AUTHOR, MANUAL = "exact_title_author", "fuzzy_title_author", "manual"


def confidence_label(score: float) -> str:
    """high >= 0.85, medium >= 0.6, low otherwise (the turath-catalog enum)."""
    return "high" if score >= 0.85 else "medium" if score >= 0.6 else "low"


@dataclass
class FileRef:
    """One file of an edition: a local PDF, an archive.org file, a Shamela PDF."""

    name: str
    size: int | None = None
    url: str = ""
    path: str = ""
    md5: str = ""
    sha1: str = ""
    format: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in ("", None)}


@dataclass
class Record:
    """A book as one source describes it. ``scheme:id`` is unique across all inputs."""

    scheme: str
    id: str
    title: str
    author: str = ""
    death: int | None = None  # Hijri year of the author's death
    editor: str = ""
    publisher: str = ""
    place: str = ""
    year: str = ""  # as printed: «1311 هـ», «1993», «1413 - 1993»
    volumes: int | None = None
    files: list[FileRef] = field(default_factory=list)
    url: str = ""
    work_uri: str = ""  # a source-given work identifier (OpenITI book URI)
    flags: set[str] = field(default_factory=set)  # thesis, manuscript, typed, part, audio
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.scheme}:{self.id}"

    @property
    def total_size(self) -> int | None:
        sizes = [f.size for f in self.files if f.size]
        return sum(sizes) if sizes else None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "scheme": self.scheme,
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "death": self.death,
            "editor": self.editor,
            "publisher": self.publisher,
            "place": self.place,
            "year": self.year,
            "volumes": self.volumes,
            "url": self.url,
            "work_uri": self.work_uri,
            "flags": sorted(self.flags),
            "files": [f.to_dict() for f in self.files],
        }
        return {k: v for k, v in d.items() if v not in ("", None, [])}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Record:
        files = [FileRef(**f) for f in d.get("files", [])]
        known = {
            k: d[k] for k in ("editor", "publisher", "place", "year", "url", "work_uri", "author") if k in d
        }
        return cls(
            scheme=d["scheme"],
            id=str(d["id"]),
            title=d["title"],
            death=d.get("death"),
            volumes=d.get("volumes"),
            files=files,
            flags=set(d.get("flags", [])),
            **known,
        )


@dataclass(frozen=True)
class Evidence:
    """One reason for (weight > 0) or against (weight < 0) a verdict. A veto has weight -1."""

    kind: str  # title author death derivation part size editor publisher volumes year flag hash bytes manual
    detail: str
    weight: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "detail": self.detail, "weight": round(self.weight, 3)}


@dataclass
class Match:
    """The comparison of two records at one level, with every reason that led to it."""

    left: Record
    right: Record
    level: str  # work | edition | file
    verdict: str
    score: float
    method: str
    evidence: list[Evidence] = field(default_factory=list)
    relation: str | None = None  # for verdict «related»: abridgement, commentary, …
    direction: str | None = None  # "left" | "right": which side is the derived work

    @property
    def confidence(self) -> str:
        return confidence_label(self.score)

    @property
    def status(self) -> str:
        if self.verdict == SAME and self.score >= 0.85:
            return MATCH
        if self.verdict == UNCERTAIN or (self.verdict == SAME and self.score >= 0.5):
            return REVIEW
        return NO_MATCH

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_scheme": self.left.scheme,
            "left_id": self.left.id,
            "right_scheme": self.right.scheme,
            "right_id": self.right.id,
            "level": self.level,
            "verdict": self.verdict,
            "relation": self.relation,
            "derived_side": self.direction,
            "method": self.method,
            "score": round(self.score, 3),
            "confidence": self.confidence,
            "status": self.status,
            "evidence": [e.to_dict() for e in self.evidence],
            "left_title": self.left.title,
            "left_author": self.left.author,
            "right_title": self.right.title,
            "right_author": self.right.author,
            "right_url": self.right.url,
        }

    def explain(self) -> str:
        """Human-readable evidence, one reason per line."""
        head = f"{self.level}: {self.verdict}"
        if self.relation:
            head += f" ({self.relation}, derived side: {self.direction})"
        head += f"  score {self.score:.2f} [{self.confidence}] -> {self.status}  via {self.method}"
        lines = [head]
        for e in self.evidence:
            sign = "+" if e.weight > 0 else "-" if e.weight < 0 else "·"
            lines.append(f"  {sign} {e.kind:<10} {e.detail}")
        return "\n".join(lines)
