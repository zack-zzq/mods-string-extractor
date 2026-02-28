"""Pack translated strings into a Minecraft resource pack."""

from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PACK_FORMAT = 34  # Minecraft 1.21.x
DEFAULT_DESCRIPTION = "Translated strings resource pack"


def _create_pack_mcmeta(
    pack_format: int = DEFAULT_PACK_FORMAT,
    description: str = DEFAULT_DESCRIPTION,
) -> str:
    """Generate pack.mcmeta content."""
    meta = {
        "pack": {
            "pack_format": pack_format,
            "description": description,
        }
    }
    return json.dumps(meta, indent=2, ensure_ascii=False) + "\n"


def _get_jar_for_modid(mods_dir: Path, target_modid: str) -> Path | None:
    """Find the jar file containing the specified modid."""
    for jar_path in mods_dir.glob("*.jar"):
        try:
            with zipfile.ZipFile(jar_path, "r") as jar:
                for name in jar.namelist():
                    parts = name.split("/")
                    if len(parts) >= 2 and parts[0] == "assets" and parts[1] == target_modid:
                        return jar_path
        except zipfile.BadZipFile:
            continue
    return None

def _replace_patchouli_strings(data: dict | list | str, translations: dict[str, str], current_path: str = "") -> dict | list | str:
    """Recursively replace string values in Patchouli JSON using the flat translations map."""
    target_keys = {"name", "text", "title", "description", "advancement_text", "subtitle", "link_text", "label"}
    
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            new_path = f"{current_path}.{k}" if current_path else k
            if k in target_keys and isinstance(v, str) and v.strip() and not v.startswith("$(macrolink"):
                if new_path in translations:
                    new_dict[k] = translations[new_path]
                else:
                    new_dict[k] = v
            elif isinstance(v, (dict, list)):
                new_dict[k] = _replace_patchouli_strings(v, translations, new_path)
            else:
                new_dict[k] = v
        return new_dict
    elif isinstance(data, list):
        new_list = []
        for i, item in enumerate(data):
            new_path = f"{current_path}[{i}]"
            if isinstance(item, str) and item.strip() and not item.startswith("$(macrolink"):
                if new_path in translations:
                    new_list.append(translations[new_path])
                else:
                    new_list.append(item)
            elif isinstance(item, (dict, list)):
                new_list.append(_replace_patchouli_strings(item, translations, new_path))
            else:
                new_list.append(item)
        return new_list
    return data


def pack_resourcepack(
    input_dir: Path,
    output_file: Path,
    pack_format: int = DEFAULT_PACK_FORMAT,
    description: str = DEFAULT_DESCRIPTION,
    mods_dir: Path | None = None,
) -> int:
    """Pack translated JSON files into a Minecraft resource pack zip.

    Expected input structure:
        input_dir/
            <modid>/
                en_us.json     (containing translated zh_cn strings)
                patchouli.json (optional)
            ...

    Output resource pack structure:
        pack.mcmeta
        assets/
            <modid>/
                lang/
                    zh_cn.json
                patchouli_books/
                    <book_name>/
                        zh_cn/
                            ...

    Args:
        input_dir: Directory containing translated JSON files.
        output_file: Output zip file path.
        pack_format: Minecraft pack format version.
        description: Resource pack description.
        mods_dir: Optional directory with original mods (needed for patchouli structure).

    Returns:
        Number of language files explicitly packed.
    """
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    file_count = 0

    with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write pack.mcmeta
        zf.writestr("pack.mcmeta", _create_pack_mcmeta(pack_format, description))

        # Walk through input directory for modid folders
        for modid_dir in sorted(input_dir.iterdir()):
            if not modid_dir.is_dir():
                continue

            modid = modid_dir.name
            lang_file = modid_dir / "en_us.json"

            if not lang_file.exists():
                logger.warning("No en_us.json found in %s, skipping", modid_dir)
                continue

            # Read and validate JSON
            try:
                content = lang_file.read_text(encoding="utf-8")
                data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning("Invalid JSON in %s: %s, skipping", lang_file, e)
                continue

            if not data:
                logger.info("Empty translation file for %s, skipping", modid)
            else:
                # Write as zh_cn.json in the resource pack
                pack_path = f"assets/{modid}/lang/zh_cn.json"
                zf.writestr(
                    pack_path,
                    json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                )
                file_count += 1
                logger.info("[%s] packed %d keys", modid, len(data))

            # Handle Patchouli
            patchouli_file = modid_dir / "patchouli.json"
            if patchouli_file.exists() and mods_dir:
                try:
                    patchouli_data = json.loads(patchouli_file.read_text(encoding="utf-8"))
                    # Map flat translations to file paths
                    # Expected key: data/<modid>/patchouli_books/manual/en_us/entries/item.json::pages[0].text
                    file_map: dict[str, dict[str, str]] = {}
                    for full_key, translation in patchouli_data.items():
                        if "::" in full_key:
                            file_path, json_path = full_key.split("::", 1)
                            file_map.setdefault(file_path, {})[json_path] = translation

                    if file_map:
                        jar_path = _get_jar_for_modid(mods_dir, modid)
                        if jar_path:
                            with zipfile.ZipFile(jar_path, "r") as jar:
                                for en_us_path, file_translations in file_map.items():
                                    try:
                                        ast_bytes = jar.read(en_us_path)
                                        ast = json.loads(ast_bytes)
                                        
                                        # Recursively replace strings
                                        localized_ast = _replace_patchouli_strings(ast, file_translations)
                                        
                                        # Construct zh_cn target path
                                        parts = en_us_path.split("/")
                                        try:
                                            en_us_idx = parts.index("en_us")
                                            parts[en_us_idx] = "zh_cn"
                                            # Also replace data/ -> assets/
                                            if parts[0] == "data":
                                                parts[0] = "assets"
                                            zh_cn_output_path = "/".join(parts)
                                            
                                            zf.writestr(
                                                zh_cn_output_path,
                                                json.dumps(localized_ast, indent=2, ensure_ascii=False) + "\n",
                                            )
                                        except ValueError:
                                            pass
                                    except Exception as e:
                                        logger.warning("Failed to localize %s: %s", en_us_path, e)
                            logger.info("[%s] packed %d patchouli files", modid, len(file_map))
                except json.JSONDecodeError as e:
                    logger.warning("Invalid JSON in patchouli %s: %s, skipping", patchouli_file, e)

    logger.info(
        "Resource pack created: %s (%d language files)", output_file, file_count
    )
    return file_count
