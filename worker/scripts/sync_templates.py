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
DEFAULT_RUNTIME_SOURCE_PATH = "src/infrastructure/reporting/web_worker_runtime"
DEFAULT_TEMPLATE_SOURCE_PATH = "src/infrastructure/reporting/templates"


def _download_archive(repo: str, ref: str) -> bytes:
    archive_url = f"https://codeload.github.com/{repo}/tar.gz/{ref}"
    print(f"[sync-worker-assets] downloading {archive_url}")
    with urllib.request.urlopen(archive_url, timeout=30) as response:
        return response.read()


def _extract_directory(
    archive: tarfile.TarFile,
    source_path: str,
    target_dir: Path,
) -> int:
    source_parts = tuple(Path(source_path).parts)
    extracted_count = 0

    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

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

    return extracted_count


def main() -> int:
    repo = (
        os.environ.get("WORKER_SOURCE_REPO")
        or os.environ.get("TEMPLATE_SOURCE_REPO")
        or DEFAULT_REPO
    ).strip()
    ref = (
        os.environ.get("WORKER_SOURCE_REF")
        or os.environ.get("TEMPLATE_SOURCE_REF")
        or DEFAULT_REF
    ).strip()
    runtime_source_path = os.environ.get(
        "WORKER_SOURCE_PATH", DEFAULT_RUNTIME_SOURCE_PATH
    ).strip("/")
    template_source_path = os.environ.get(
        "TEMPLATE_SOURCE_PATH", DEFAULT_TEMPLATE_SOURCE_PATH
    ).strip("/")

    if not repo or "/" not in repo:
        raise SystemExit("invalid WORKER_SOURCE_REPO")
    if not ref:
        raise SystemExit("invalid WORKER_SOURCE_REF")
    if not runtime_source_path:
        raise SystemExit("invalid WORKER_SOURCE_PATH")
    if not template_source_path:
        raise SystemExit("invalid TEMPLATE_SOURCE_PATH")

    root_dir = Path(__file__).resolve().parents[1]
    target_runtime_dir = root_dir / "src"
    target_template_dir = root_dir / "templates"
    archive_data = _download_archive(repo, ref)

    with tarfile.open(fileobj=io.BytesIO(archive_data), mode="r:gz") as archive:
        extracted_runtime = _extract_directory(
            archive, runtime_source_path, target_runtime_dir
        )
    with tarfile.open(fileobj=io.BytesIO(archive_data), mode="r:gz") as archive:
        extracted_templates = _extract_directory(
            archive, template_source_path, target_template_dir
        )

    if extracted_runtime == 0:
        raise SystemExit(
            f"no runtime extracted from {repo}@{ref}:{runtime_source_path}"
        )
    if extracted_templates == 0:
        raise SystemExit(
            f"no templates extracted from {repo}@{ref}:{template_source_path}"
        )

    print(
        "[sync-worker-assets] extracted "
        f"{extracted_runtime} runtime files and {extracted_templates} templates "
        f"from {repo}@{ref}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
