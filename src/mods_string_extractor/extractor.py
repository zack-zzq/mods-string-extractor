"""Extract translatable strings from Minecraft mod jar files."""

from __future__ import annotations

import json
import logging
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of extracting strings from a single mod jar."""

    jar_name: str
    namespaces: dict[str, dict[str, str]] = field(default_factory=dict)
    """Mapping of modid -> {key: en_us_value} for untranslated strings."""

    @property
    def total_keys(self) -> int:
        return sum(len(v) for v in self.namespaces.values())


def _find_lang_namespaces(jar: zipfile.ZipFile) -> dict[str, list[str]]:
    """Find all mod namespaces that have lang files in the jar.

    Returns a dict of modid -> list of lang file paths.
    """
    namespaces: dict[str, list[str]] = {}
    for name in jar.namelist():
        # Match pattern: assets/<modid>/lang/<file>.json
        parts = name.split("/")
        if (
            len(parts) == 4
            and parts[0] == "assets"
            and parts[2] == "lang"
            and parts[3].endswith(".json")
        ):
            modid = parts[1]
            namespaces.setdefault(modid, []).append(name)
    return namespaces


def _read_json_from_jar(jar: zipfile.ZipFile, path: str) -> dict[str, str]:
    """Read and parse a JSON lang file from inside a jar."""
    try:
        data = jar.read(path)
        return json.loads(data)
    except (KeyError, json.JSONDecodeError) as e:
        logger.warning("Failed to read %s: %s", path, e)
        return {}


def extract_mod(jar_path: Path) -> ExtractionResult:
    """Extract untranslated strings from a single mod jar file.

    For each namespace (modid) found in the jar:
    - If zh_cn.json exists: extract keys present in en_us.json but missing from zh_cn.json
    - If zh_cn.json does not exist: extract all keys from en_us.json
    """
    result = ExtractionResult(jar_name=jar_path.name)

    try:
        with zipfile.ZipFile(jar_path, "r") as jar:
            namespaces = _find_lang_namespaces(jar)

            for modid, lang_files in namespaces.items():
                en_us_path = f"assets/{modid}/lang/en_us.json"
                zh_cn_path = f"assets/{modid}/lang/zh_cn.json"

                if en_us_path not in lang_files:
                    continue

                en_us = _read_json_from_jar(jar, en_us_path)
                if not en_us:
                    continue

                if zh_cn_path in lang_files:
                    # Diff mode: only extract keys missing from zh_cn
                    zh_cn = _read_json_from_jar(jar, zh_cn_path)
                    diff = {k: v for k, v in en_us.items() if k not in zh_cn}
                    if diff:
                        result.namespaces[modid] = diff
                        logger.info(
                            "[%s/%s] %d/%d keys need translation",
                            jar_path.name,
                            modid,
                            len(diff),
                            len(en_us),
                        )
                    else:
                        logger.info(
                            "[%s/%s] fully translated, skipping",
                            jar_path.name,
                            modid,
                        )
                else:
                    # Full mode: extract all en_us keys
                    result.namespaces[modid] = en_us
                    logger.info(
                        "[%s/%s] no zh_cn found, extracting all %d keys",
                        jar_path.name,
                        modid,
                        len(en_us),
                    )

    except zipfile.BadZipFile:
        logger.warning("Skipping invalid jar: %s", jar_path.name)
    except Exception as e:
        logger.warning("Error processing %s: %s", jar_path.name, e)

    return result


def extract_mods(mods_dir: Path, output_dir: Path) -> list[ExtractionResult]:
    """Extract untranslated strings from all mod jars in a directory.

    Args:
        mods_dir: Directory containing .jar files.
        output_dir: Directory to write extracted JSON files to.

    Returns:
        List of extraction results.
    """
    if not mods_dir.is_dir():
        raise FileNotFoundError(f"Mods directory not found: {mods_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    jar_files = sorted(mods_dir.glob("*.jar"))
    if not jar_files:
        logger.warning("No .jar files found in %s", mods_dir)
        return []

    logger.info("Found %d jar files in %s", len(jar_files), mods_dir)

    results: list[ExtractionResult] = []
    total_keys = 0

    for jar_path in jar_files:
        result = extract_mod(jar_path)
        results.append(result)

        for modid, strings in result.namespaces.items():
            mod_output_dir = output_dir / modid
            mod_output_dir.mkdir(parents=True, exist_ok=True)
            output_file = mod_output_dir / "en_us.json"

            # If the file already exists (from another jar), merge keys
            if output_file.exists():
                existing = json.loads(output_file.read_text(encoding="utf-8"))
                existing.update(strings)
                strings = existing

            output_file.write_text(
                json.dumps(strings, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            total_keys += len(strings)

    logger.info(
        "Extraction complete: %d mods processed, %d namespaces, %d total keys",
        len(results),
        sum(len(r.namespaces) for r in results),
        total_keys,
    )

    return results
