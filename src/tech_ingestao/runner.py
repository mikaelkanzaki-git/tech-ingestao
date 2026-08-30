"""Interface de linha de comando do serviço de ingestão."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from tech_ingestao.config.dependencies import (
    build_chroma_repository,
    build_knowledge_index_service,
)
from tech_ingestao.errors import (
    ConfigurationError,
    DatasetPreparationError,
    EmbeddingError,
    KnowledgeIndexError,
    KnowledgeStoreError,
    ScanError,
)
from tech_ingestao.integrations.filesystem.report_writer import write_json, write_jsonl
from tech_ingestao.services.dataset_preparation_service import (
    SplitConfig,
    prepare_medquad_dataset,
)
from tech_ingestao.services.scan_service import scan_medquad


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("o valor deve ser maior que zero")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tech-ingestao",
        description="Prepara e ingere fontes médicas para o Tech Challenge.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    scan_parser = subcommands.add_parser(
        "scan",
        help="Varre o MedQuAD e gera um relatório de qualidade.",
    )
    scan_parser.add_argument(
        "--source",
        type=Path,
        default=Path("../MedQuAD"),
        help="Diretório raiz do MedQuAD (padrão: ../MedQuAD).",
    )
    scan_parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/scan"),
        help="Diretório dos relatórios (padrão: artifacts/scan).",
    )

    prepare_parser = subcommands.add_parser(
        "prepare",
        help="Gera o dataset canônico e os splits sem vazamento.",
    )
    prepare_parser.add_argument(
        "--source",
        type=Path,
        default=Path("../MedQuAD"),
        help="Diretório raiz do MedQuAD (padrão: ../MedQuAD).",
    )
    prepare_parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/dataset"),
        help="Diretório do dataset preparado (padrão: artifacts/dataset).",
    )
    prepare_parser.add_argument("--train-ratio", type=float, default=0.8)
    prepare_parser.add_argument("--validation-ratio", type=float, default=0.1)
    prepare_parser.add_argument("--test-ratio", type=float, default=0.1)
    prepare_parser.add_argument("--seed", type=int, default=42)

    index_parser = subcommands.add_parser(
        "index",
        help="Gera embeddings pela OpenAI e faz upsert no ChromaDB.",
    )
    index_parser.add_argument(
        "--source",
        type=Path,
        default=Path("../MedQuAD"),
        help="Diretório raiz do MedQuAD (padrão: ../MedQuAD).",
    )
    index_parser.add_argument(
        "--split",
        choices=("train", "validation", "test"),
        default="train",
        help="Split a indexar (padrão: train).",
    )
    index_parser.add_argument(
        "--batch-size",
        type=_positive_integer,
        default=100,
        help="Registros enviados por lote (padrão: 100).",
    )
    index_parser.add_argument(
        "--limit",
        type=_positive_integer,
        help="Limita registros para smoke tests; omita para indexar todo o split.",
    )

    search_parser = subcommands.add_parser(
        "search",
        help="Executa uma consulta semântica na coleção configurada.",
    )
    search_parser.add_argument("query", help="Pergunta ou texto usado na busca.")
    search_parser.add_argument("--limit", type=_positive_integer, default=5)

    subcommands.add_parser(
        "chroma-health",
        help="Valida a conexão com o ChromaDB sem chamar a OpenAI.",
    )
    return parser


def _run_scan(source: Path, output: Path) -> int:
    result = scan_medquad(source)
    report_path = output / "report.json"
    rejected_path = output / "rejected.jsonl"
    write_json(report_path, result.report)
    write_jsonl(rejected_path, result.rejected_records)

    summary = result.report["summary"]
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"Relatório: {report_path.resolve()}")
    print(f"Rejeitados: {rejected_path.resolve()}")
    return 0


def _run_prepare(
    source: Path,
    output: Path,
    *,
    train_ratio: float,
    validation_ratio: float,
    test_ratio: float,
    seed: int,
) -> int:
    prepared = prepare_medquad_dataset(
        source,
        config=SplitConfig(
            train_ratio=train_ratio,
            validation_ratio=validation_ratio,
            test_ratio=test_ratio,
            seed=seed,
        ),
    )
    write_jsonl(output / "canonical.jsonl", (item.as_dict() for item in prepared.canonical_records))
    write_jsonl(output / "train.jsonl", (item.as_dict() for item in prepared.train_records))
    write_jsonl(
        output / "validation.jsonl",
        (item.as_dict() for item in prepared.validation_records),
    )
    write_jsonl(output / "test.jsonl", (item.as_dict() for item in prepared.test_records))
    write_jsonl(
        output / "duplicates.jsonl",
        (item.as_dict() for item in prepared.duplicate_removals),
    )
    write_jsonl(
        output / "pii-audit.jsonl",
        (item.as_dict() for item in prepared.pii_findings),
    )
    write_json(output / "manifest.json", prepared.manifest)

    print(json.dumps(prepared.manifest["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    print(f"Dataset: {output.resolve()}")
    return 0


def _run_index(
    source: Path,
    *,
    split: str,
    batch_size: int,
    limit: int | None,
) -> int:
    prepared = prepare_medquad_dataset(source)
    records_by_split = {
        "train": prepared.train_records,
        "validation": prepared.validation_records,
        "test": prepared.test_records,
    }
    records = records_by_split[split]
    if limit is not None:
        records = records[:limit]

    summary = build_knowledge_index_service().index(
        records,
        split=split,
        batch_size=batch_size,
    )
    print(json.dumps(summary.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _run_search(query: str, *, limit: int) -> int:
    results = build_knowledge_index_service().search(query, limit=limit)
    print(
        json.dumps(
            [result.as_dict() for result in results],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _run_chroma_health() -> int:
    repository = build_chroma_repository()
    print(json.dumps({"status": "ok", "collection_records": repository.count()}, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "scan":
            return _run_scan(arguments.source, arguments.output)
        if arguments.command == "prepare":
            return _run_prepare(
                arguments.source,
                arguments.output,
                train_ratio=arguments.train_ratio,
                validation_ratio=arguments.validation_ratio,
                test_ratio=arguments.test_ratio,
                seed=arguments.seed,
            )
        if arguments.command == "index":
            return _run_index(
                arguments.source,
                split=arguments.split,
                batch_size=arguments.batch_size,
                limit=arguments.limit,
            )
        if arguments.command == "search":
            return _run_search(arguments.query, limit=arguments.limit)
        if arguments.command == "chroma-health":
            return _run_chroma_health()
    except (
        ConfigurationError,
        DatasetPreparationError,
        EmbeddingError,
        KnowledgeIndexError,
        KnowledgeStoreError,
        ScanError,
    ) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 2

    parser.error(f"Comando desconhecido: {arguments.command}")
    return 2
