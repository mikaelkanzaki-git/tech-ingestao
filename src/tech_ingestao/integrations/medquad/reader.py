"""Leitor dos formatos XML publicados pelo MedQuAD."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from tech_ingestao.models.medquad import MedQuADDocument, MedQuADQuestionAnswer

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element


_WHITESPACE = re.compile(r"\s+")


class MalformedMedQuADDocumentError(ValueError):
    """Indica que um documento do MedQuAD não pôde ser lido."""


def normalize_text(value: str | None) -> str:
    """Remove espaços redundantes sem alterar pontuação ou capitalização."""

    return _WHITESPACE.sub(" ", value or "").strip()


def _element_text(element: Element[str] | None) -> str:
    if element is None:
        return ""
    return normalize_text(" ".join(element.itertext()))


def _first_element(parent: Element[str], *paths: str) -> Element[str] | None:
    for path in paths:
        element = parent.find(path)
        if element is not None:
            return element
    return None


def _first_attribute(element: Element[str], *names: str) -> str | None:
    for name in names:
        value = normalize_text(element.get(name))
        if value:
            return value
    return None


def _unique_texts(root: Element[str], *paths: str) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for path in paths:
        for element in root.findall(path):
            value = _element_text(element)
            if value and value not in seen:
                values.append(value)
                seen.add(value)
    return tuple(values)


class MedQuADReader:
    """Descobre e converte os formatos atual e legado do MedQuAD."""

    def discover(self, source_root: Path) -> tuple[Path, ...]:
        return tuple(
            sorted(
                source_root.rglob("*.xml"),
                key=lambda item: item.relative_to(source_root).as_posix(),
            )
        )

    def read(self, xml_path: Path) -> MedQuADDocument:
        try:
            root = ET.parse(xml_path).getroot()
        except (ET.ParseError, DefusedXmlException, OSError, UnicodeError) as error:
            raise MalformedMedQuADDocumentError(str(error)) from error
        assert root is not None

        pair_elements = [*root.findall(".//QAPair"), *root.findall(".//pair")]
        pairs: list[MedQuADQuestionAnswer] = []
        for position, pair in enumerate(pair_elements, start=1):
            question_element = _first_element(pair, "Question", "question")
            answer_element = _first_element(pair, "Answer", "answer")
            pairs.append(
                MedQuADQuestionAnswer(
                    position=position,
                    pair_id=_first_attribute(pair, "pid"),
                    question_id=(
                        _first_attribute(question_element, "qid")
                        if question_element is not None
                        else None
                    ),
                    question_type=(
                        _first_attribute(question_element, "qtype")
                        if question_element is not None
                        else None
                    ),
                    question=_element_text(question_element),
                    answer=_element_text(answer_element),
                )
            )

        return MedQuADDocument(
            document_id=_first_attribute(root, "id", "docid", "fid"),
            publisher=_first_attribute(root, "source", "corpus"),
            source_url=_first_attribute(root, "url"),
            focus=_element_text(_first_element(root, "Focus", "doctitle-focus")) or None,
            category=(
                _element_text(_first_element(root, "./FocusAnnotations/Category", "Category"))
                or None
            ),
            synonyms=_unique_texts(root, ".//Synonym", ".//synonym"),
            umls_cuis=_unique_texts(root, ".//CUI", ".//cui"),
            umls_semantic_types=_unique_texts(
                root,
                ".//SemanticType",
                ".//semanticType",
            ),
            umls_semantic_groups=_unique_texts(
                root,
                ".//SemanticGroup",
                ".//semanticGroup",
            ),
            pairs=tuple(pairs),
        )
