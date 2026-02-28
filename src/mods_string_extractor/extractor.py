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
    
    patchouli: dict[str, dict[str, str]] = field(default_factory=dict)
    """Mapping of modid -> {file_path: en_us_value} for patchouli books."""

    @property
    def total_keys(self) -> int:
        return sum(len(v) for v in self.namespaces.values()) + sum(len(v) for v in self.patchouli.values())


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

def _find_patchouli_files(jar: zipfile.ZipFile) -> dict[str, list[str]]:
    """Find all patchouli book en_us json files in the jar.

    Returns a dict of modid -> list of en_us json file paths.
    """
    patchouli_files: dict[str, list[str]] = {}
    for name in jar.namelist():
        # Match pattern: data/<modid>/patchouli_books/<book...>/en_us/**/*.json
        parts = name.split("/")
        if len(parts) >= 6 and parts[0] == "data" and parts[2] == "patchouli_books":
            # Finding the en_us part of the hierarchy
            try:
                en_us_idx = parts.index("en_us")
                if parts[-1].endswith(".json"):
                    modid = parts[1]
                    patchouli_files.setdefault(modid, []).append(name)
            except ValueError:
                pass
    return patchouli_files

def _extract_patchouli_strings(data: dict | list | str, path: str = "") -> dict[str, str]:
    """Recursively extract translatable strings from Patchouli JSON AST."""
    strings = {}
    target_keys = {"name", "text", "title", "description", "advancement_text", "subtitle", "link_text", "label"}
    
    if isinstance(data, dict):
        for k, v in data.items():
            new_path = f"{path}.{k}" if path else k
            if k in target_keys and isinstance(v, str) and v.strip():
                # Don't translate pure macro calls or empty strings
                if not v.startswith("$(macrolink"):
                    strings[new_path] = v
            elif isinstance(v, (dict, list)):
                strings.update(_extract_patchouli_strings(v, new_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            new_path = f"{path}[{i}]"
            if isinstance(item, (dict, list, str)):
                if isinstance(item, str) and item.strip() and not item.startswith("$(macrolink"):
                     strings[new_path] = item
                else:
                    strings.update(_extract_patchouli_strings(item, new_path))
            
    return strings


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

            # --- Patchouli Extraction ---
            patchouli_files = _find_patchouli_files(jar)
            for modid, en_us_paths in patchouli_files.items():
                mod_patchouli = {}
                for en_us_path in en_us_paths:
                    # Deriving the zh_cn equivalent path
                    parts = en_us_path.split("/")
                    en_us_idx = parts.index("en_us")
                    zh_cn_parts = list(parts)
                    zh_cn_parts[en_us_idx] = "zh_cn"
                    zh_cn_path = "/".join(zh_cn_parts)
                    
                    en_ast = _read_json_from_jar(jar, en_us_path)
                    if not en_ast:
                        continue
                        
                    en_strings = _extract_patchouli_strings(en_ast)
                    if not en_strings:
                        continue
                        
                    zh_strings = {}
                    if zh_cn_path in jar.namelist():
                        zh_ast = _read_json_from_jar(jar, zh_cn_path)
                        zh_strings = _extract_patchouli_strings(zh_ast)
                    
                    # Prefix with file path to resolve uniqueness across multiple files
                    # Example key: "data/my_mod/patchouli_books/manual/en_us/entries/intro.json::pages[0].text"
                    for json_path, string_val in en_strings.items():
                        if json_path not in zh_strings or zh_strings[json_path] == string_val:
                            # It's either missing in zh_cn OR it's present in zh_cn but still untranslated (equals en_us)
                            flat_key = f"{en_us_path}::{json_path}"
                            mod_patchouli[flat_key] = string_val
                            
                if mod_patchouli:
                    result.patchouli[modid] = mod_patchouli
                    logger.info(
                        "[%s/%s] extracted %d patchouli translatable strings",
                        jar_path.name, modid, len(mod_patchouli)
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

        for modid, patchouli_strings in result.patchouli.items():
            mod_output_dir = output_dir / modid
            mod_output_dir.mkdir(parents=True, exist_ok=True)
            output_file = mod_output_dir / "patchouli.json"

            if output_file.exists():
                existing = json.loads(output_file.read_text(encoding="utf-8"))
                existing.update(patchouli_strings)
                patchouli_strings = existing

            output_file.write_text(
                json.dumps(patchouli_strings, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            total_keys += len(patchouli_strings)

    logger.info(
        "Extraction complete: %d mods processed, %d namespaces, %d total keys",
        len(results),
        sum(len(r.namespaces) for r in results),
        total_keys,
    )

    return results
