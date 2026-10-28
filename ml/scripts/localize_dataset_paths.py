"""Починка путей в датасете после переноса с обучающего хоста.

Фолды собраны симлинками на общий пул кадров, и ссылки эти АБСОЛЮТНЫЕ
(`/home/alex/dumps_monitoring/ml/data/processed/to_label/<cam>/…`), плюс в
каждом `data.yaml` прописан абсолютный `path:`. После rsync на другую машину
и то и другое указывает в пустоту.

Скрипт: (1) переписывает симлинки на ОТНОСИТЕЛЬНЫЕ — тогда дерево переносимо
куда угодно и повторять эту починку больше не придётся; (2) правит `path:` в
data.yaml на текущий корень; (3) считает битые ссылки, чтобы молча не
проехать мимо недокачанных кадров.

Идемпотентен: повторный запуск ничего не портит.
"""

import argparse
import os
import sys
from pathlib import Path

ML_ROOT = Path(__file__).resolve().parent.parent
OLD_ROOTS = ("/home/alex/dumps_monitoring/ml", "/home/andre/dumps_monitoring/ml")


def fix_symlinks(data_dir: Path, dry: bool) -> tuple[int, int]:
    fixed = broken = 0
    for link in data_dir.rglob("*"):
        if not link.is_symlink():
            continue
        target = os.readlink(link)
        for old in OLD_ROOTS:
            if target.startswith(old):
                new_abs = ML_ROOT / target[len(old):].lstrip("/")
                rel = os.path.relpath(new_abs, link.parent)
                if not dry:
                    link.unlink()
                    link.symlink_to(rel)
                fixed += 1
                target = rel
                break
        if not (link.parent / target).exists():
            broken += 1
    return fixed, broken


def fix_yamls(data_dir: Path, dry: bool) -> int:
    fixed = 0
    for yaml in data_dir.rglob("data.yaml"):
        text = yaml.read_text()
        new = text
        for old in OLD_ROOTS:
            new = new.replace(old, str(ML_ROOT))
        if new != text:
            if not dry:
                yaml.write_text(new)
            fixed += 1
    return fixed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data_dir = ML_ROOT / "data"
    if not data_dir.is_dir():
        print(f"нет каталога {data_dir}", file=sys.stderr)
        return 1

    links, broken = fix_symlinks(data_dir, args.dry_run)
    yamls = fix_yamls(data_dir, args.dry_run)

    print(f"корень: {ML_ROOT}")
    print(f"симлинков переписано на относительные: {links}")
    print(f"data.yaml исправлено: {yamls}")
    if broken:
        print(f"ВНИМАНИЕ: битых ссылок осталось {broken} — кадры не докачаны "
              f"или лежат не там", file=sys.stderr)
        return 1
    print("битых ссылок нет")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
