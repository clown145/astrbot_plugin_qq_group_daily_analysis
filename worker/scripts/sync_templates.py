#!/usr/bin/env python3
from __future__ import annotations

import io
import os
import shutil
import tarfile
import urllib.request
from pathlib import Path

DEFAULT_REPO = "SXP-Simon/astrbot_plugin_qq_group_daily_analysis"
DEFAULT_REF = "main"
DEFAULT_SOURCE_PATH = "src/infrastructure/reporting/templates"


def main() -> int:
    repo = os.environ.get("TEMPLATE_SOURCE_REPO", DEFAULT_REPO).strip()
    ref = os.environ.get("TEMPLATE_SOURCE_REF", DEFAULT_REF).strip()
    source_path = os.environ.get("TEMPLATE_SOURCE_PATH", DEFAULT_SOURCE_PATH).strip("/")

    if not repo or "/" not in repo:
        raise SystemExit("invalid TEMPLATE_SOURCE_REPO")
    if not ref:
        raise SystemExit("invalid TEMPLATE_SOURCE_REF")
    if not source_path:
        raise SystemExit("invalid TEMPLATE_SOURCE_PATH")

    root_dir = Path(__file__).resolve().parents[1]
    target_dir = root_dir / "templates"

    archive_url = f"https://codeload.github.com/{repo}/tar.gz/{ref}"
    print(f"[sync-templates] downloading {archive_url}")

    with urllib.request.urlopen(archive_url, timeout=30) as response:
        archive_data = response.read()

    source_parts = tuple(Path(source_path).parts)
    extracted_count = 0

    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(fileobj=io.BytesIO(archive_data), mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue

            member_parts = Path(member.name).parts
            if len(member_parts) <= len(source_parts):
                continue
            if tuple(member_parts[1 : 1 + len(source_parts)]) != source_parts:
                continue

            relative_parts = member_parts[1 + len(source_parts) :]
            if not relative_parts:
                continue

            destination = target_dir.joinpath(*relative_parts)
            destination.parent.mkdir(parents=True, exist_ok=True)

            extracted_file = archive.extractfile(member)
            if extracted_file is None:
                continue

            destination.write_bytes(extracted_file.read())
            extracted_count += 1

    if extracted_count == 0:
        raise SystemExit(f"no templates extracted from {repo}@{ref}:{source_path}")

    print(
        f"[sync-templates] extracted {extracted_count} files from "
        f"{repo}@{ref}:{source_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
