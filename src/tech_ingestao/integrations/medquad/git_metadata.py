"""Leitura da origem e da revisão Git do dataset."""

from __future__ import annotations

import configparser
import re
from pathlib import Path

from tech_ingestao.models.medquad import GitSourceMetadata

_COMMIT_HASH = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def _read_revision(git_dir: Path) -> str | None:
    head_path = git_dir / "HEAD"
    if not head_path.exists():
        return None

    head = head_path.read_text(encoding="utf-8").strip()
    if _COMMIT_HASH.fullmatch(head):
        return head
    if not head.startswith("ref: "):
        return None

    reference = head.removeprefix("ref: ").strip()
    reference_path = git_dir / reference
    if reference_path.exists():
        candidate = reference_path.read_text(encoding="utf-8").strip()
        return candidate if _COMMIT_HASH.fullmatch(candidate) else None

    packed_refs = git_dir / "packed-refs"
    if not packed_refs.exists():
        return None
    for line in packed_refs.read_text(encoding="utf-8").splitlines():
        if line.endswith(f" {reference}"):
            candidate = line.split(" ", maxsplit=1)[0]
            return candidate if _COMMIT_HASH.fullmatch(candidate) else None
    return None


def _read_repository(git_dir: Path) -> str | None:
    config_path = git_dir / "config"
    if not config_path.exists():
        return None

    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")
    return config.get('remote "origin"', "url", fallback=None)


def read_git_metadata(source_root: Path) -> GitSourceMetadata:
    """Obtém metadados Git sem executar comandos externos."""

    git_dir = source_root / ".git"
    if not git_dir.is_dir():
        return GitSourceMetadata(repository=None, revision=None)
    return GitSourceMetadata(
        repository=_read_repository(git_dir),
        revision=_read_revision(git_dir),
    )
