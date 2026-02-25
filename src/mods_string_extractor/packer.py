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


def pack_resourcepack(
    input_dir: Path,
    output_file: Path,
    pack_format: int = DEFAULT_PACK_FORMAT,
    description: str = DEFAULT_DESCRIPTION,
) -> int:
    """Pack translated JSON files into a Minecraft resource pack zip.

    Expected input structure:
        input_dir/
            <modid>/
                en_us.json   (containing translated zh_cn strings)
            ...

    Output resource pack structure:
        pack.mcmeta
        assets/
            <modid>/
                lang/
                    zh_cn.json

    Args:
        input_dir: Directory containing translated JSON files.
        output_file: Output zip file path.
        pack_format: Minecraft pack format version.
        description: Resource pack description.

    Returns:
        Number of language files packed.
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
                continue

            # Write as zh_cn.json in the resource pack
            pack_path = f"assets/{modid}/lang/zh_cn.json"
            zf.writestr(
                pack_path,
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            )
            file_count += 1
            logger.info("[%s] packed %d keys", modid, len(data))

    logger.info(
        "Resource pack created: %s (%d language files)", output_file, file_count
    )
    return file_count
