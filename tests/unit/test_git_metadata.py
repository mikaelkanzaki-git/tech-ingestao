from __future__ import annotations

from pathlib import Path

from tech_ingestao.integrations.medquad.git_metadata import read_git_metadata

REVISION = "0123456789abcdef0123456789abcdef01234567"


def test_returns_empty_metadata_without_git_directory(tmp_path: Path) -> None:
    metadata = read_git_metadata(tmp_path)

    assert metadata.repository is None
    assert metadata.revision is None


def test_reads_detached_revision_and_origin(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text(REVISION, encoding="utf-8")
    (git_dir / "config").write_text(
        '[remote "origin"]\n\turl = https://github.com/abachaa/MedQuAD.git\n',
        encoding="utf-8",
    )

    metadata = read_git_metadata(tmp_path)

    assert metadata.revision == REVISION
    assert metadata.repository == "https://github.com/abachaa/MedQuAD.git"


def test_reads_revision_from_reference_file(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    reference = git_dir / "refs" / "heads" / "main"
    reference.parent.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    reference.write_text(REVISION, encoding="utf-8")

    assert read_git_metadata(tmp_path).revision == REVISION


def test_reads_revision_from_packed_refs(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "packed-refs").write_text(
        f"# pack-refs with: peeled fully-peeled sorted\n{REVISION} refs/heads/main\n",
        encoding="utf-8",
    )

    assert read_git_metadata(tmp_path).revision == REVISION


def test_ignores_invalid_head(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("invalid", encoding="utf-8")

    assert read_git_metadata(tmp_path).revision is None
