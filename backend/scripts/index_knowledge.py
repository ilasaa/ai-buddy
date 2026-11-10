"""Index synthetic Markdown. One atomic transaction per document."""

import argparse
from pathlib import Path

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.knowledge import index_file


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--directory", type=Path, default=Path(__file__).resolve().parents[1] / "knowledge"
    )
    args = parser.parse_args()
    # Explicit CLI operation may download the model. Server remains local-only.
    settings.embedding_local_only = False
    errors = 0
    indexed = unchanged = total_chunks = 0
    files = sorted(args.directory.rglob("*.md"))
    if not files:
        raise SystemExit("Markdown-документы не найдены")
    for path in files:
        try:
            with SessionLocal.begin() as db:
                status, count = index_file(db, path, args.directory)
            indexed += status == "indexed"
            unchanged += status == "unchanged"
            total_chunks += count
            print(f"{path.name}: {status}, chunks={count}")
        except Exception as exc:
            errors += 1
            print(f"{path.name}: ошибка ({type(exc).__name__}); изменения документа отменены")
    print(
        f"Итого: обновлено {indexed}, без изменений {unchanged}, новых фрагментов {total_chunks}, ошибок {errors}"
    )
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
