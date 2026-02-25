"""Tests for mods_string_extractor."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from mods_string_extractor.extractor import ExtractionResult, extract_mod, extract_mods
from mods_string_extractor.packer import pack_resourcepack


def _create_test_jar(
    jar_path: Path,
    modid: str,
    en_us: dict[str, str],
    zh_cn: dict[str, str] | None = None,
) -> None:
    """Create a test jar file with lang files."""
    with zipfile.ZipFile(jar_path, "w") as zf:
        zf.writestr(
            f"assets/{modid}/lang/en_us.json",
            json.dumps(en_us, ensure_ascii=False),
        )
        if zh_cn is not None:
            zf.writestr(
                f"assets/{modid}/lang/zh_cn.json",
                json.dumps(zh_cn, ensure_ascii=False),
            )


class TestExtractMod:
    """Tests for extract_mod function."""

    def test_extract_full_no_zhcn(self, tmp_path: Path) -> None:
        """When no zh_cn.json exists, all en_us keys should be extracted."""
        en_us = {"item.test.sword": "Iron Sword", "item.test.shield": "Wooden Shield"}
        jar_path = tmp_path / "test-mod.jar"
        _create_test_jar(jar_path, "testmod", en_us)

        result = extract_mod(jar_path)

        assert result.jar_name == "test-mod.jar"
        assert "testmod" in result.namespaces
        assert result.namespaces["testmod"] == en_us
        assert result.total_keys == 2

    def test_extract_diff_with_zhcn(self, tmp_path: Path) -> None:
        """When zh_cn.json exists, only missing keys should be extracted."""
        en_us = {
            "item.test.sword": "Iron Sword",
            "item.test.shield": "Wooden Shield",
            "item.test.bow": "Long Bow",
        }
        zh_cn = {
            "item.test.sword": "铁剑",
            "item.test.shield": "木盾",
        }
        jar_path = tmp_path / "test-mod.jar"
        _create_test_jar(jar_path, "testmod", en_us, zh_cn)

        result = extract_mod(jar_path)

        assert "testmod" in result.namespaces
        assert result.namespaces["testmod"] == {"item.test.bow": "Long Bow"}
        assert result.total_keys == 1

    def test_extract_empty_diff(self, tmp_path: Path) -> None:
        """When zh_cn covers all en_us keys, nothing should be extracted."""
        en_us = {"item.test.sword": "Iron Sword"}
        zh_cn = {"item.test.sword": "铁剑"}
        jar_path = tmp_path / "test-mod.jar"
        _create_test_jar(jar_path, "testmod", en_us, zh_cn)

        result = extract_mod(jar_path)

        assert result.namespaces == {}
        assert result.total_keys == 0

    def test_extract_multiple_namespaces(self, tmp_path: Path) -> None:
        """A jar with multiple modids should extract all of them."""
        jar_path = tmp_path / "multi-mod.jar"
        with zipfile.ZipFile(jar_path, "w") as zf:
            zf.writestr(
                "assets/mod_a/lang/en_us.json",
                json.dumps({"key.a": "Value A"}),
            )
            zf.writestr(
                "assets/mod_b/lang/en_us.json",
                json.dumps({"key.b": "Value B"}),
            )

        result = extract_mod(jar_path)

        assert "mod_a" in result.namespaces
        assert "mod_b" in result.namespaces
        assert result.total_keys == 2

    def test_extract_invalid_jar(self, tmp_path: Path) -> None:
        """Invalid jar files should be skipped gracefully."""
        jar_path = tmp_path / "bad.jar"
        jar_path.write_text("not a zip file")

        result = extract_mod(jar_path)

        assert result.namespaces == {}
        assert result.total_keys == 0

    def test_extract_no_lang_files(self, tmp_path: Path) -> None:
        """Jars without lang files should return empty result."""
        jar_path = tmp_path / "no-lang.jar"
        with zipfile.ZipFile(jar_path, "w") as zf:
            zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")

        result = extract_mod(jar_path)

        assert result.namespaces == {}


class TestExtractMods:
    """Tests for extract_mods function."""

    def test_extract_multiple_jars(self, tmp_path: Path) -> None:
        """Test extracting from a directory of multiple jars."""
        mods_dir = tmp_path / "mods"
        mods_dir.mkdir()
        output_dir = tmp_path / "output"

        _create_test_jar(
            mods_dir / "mod-a.jar", "moda", {"key.a1": "A1", "key.a2": "A2"}
        )
        _create_test_jar(
            mods_dir / "mod-b.jar",
            "modb",
            {"key.b1": "B1", "key.b2": "B2"},
            {"key.b1": "B1中文"},
        )

        results = extract_mods(mods_dir, output_dir)

        assert len(results) == 2

        # Check mod-a: full extraction
        moda_file = output_dir / "moda" / "en_us.json"
        assert moda_file.exists()
        moda_data = json.loads(moda_file.read_text(encoding="utf-8"))
        assert moda_data == {"key.a1": "A1", "key.a2": "A2"}

        # Check mod-b: diff extraction
        modb_file = output_dir / "modb" / "en_us.json"
        assert modb_file.exists()
        modb_data = json.loads(modb_file.read_text(encoding="utf-8"))
        assert modb_data == {"key.b2": "B2"}

    def test_extract_mods_missing_dir(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for missing mods directory."""
        with pytest.raises(FileNotFoundError):
            extract_mods(tmp_path / "nonexistent", tmp_path / "output")


class TestPackResourcepack:
    """Tests for pack_resourcepack function."""

    def test_pack_basic(self, tmp_path: Path) -> None:
        """Test basic resource pack creation."""
        input_dir = tmp_path / "translations"
        modid_dir = input_dir / "testmod"
        modid_dir.mkdir(parents=True)
        (modid_dir / "en_us.json").write_text(
            json.dumps({"item.test.sword": "铁剑"}, ensure_ascii=False),
            encoding="utf-8",
        )

        output_file = tmp_path / "resourcepack.zip"
        file_count = pack_resourcepack(input_dir, output_file)

        assert file_count == 1
        assert output_file.exists()

        with zipfile.ZipFile(output_file) as zf:
            names = zf.namelist()
            assert "pack.mcmeta" in names
            assert "assets/testmod/lang/zh_cn.json" in names

            # Verify pack.mcmeta
            meta = json.loads(zf.read("pack.mcmeta"))
            assert meta["pack"]["pack_format"] == 34

            # Verify lang file content
            lang = json.loads(zf.read("assets/testmod/lang/zh_cn.json"))
            assert lang["item.test.sword"] == "铁剑"

    def test_pack_multiple_mods(self, tmp_path: Path) -> None:
        """Test packing multiple mods into one resource pack."""
        input_dir = tmp_path / "translations"
        for modid in ["mod_a", "mod_b", "mod_c"]:
            d = input_dir / modid
            d.mkdir(parents=True)
            (d / "en_us.json").write_text(
                json.dumps({f"key.{modid}": f"翻译_{modid}"}, ensure_ascii=False),
                encoding="utf-8",
            )

        output_file = tmp_path / "resourcepack.zip"
        file_count = pack_resourcepack(input_dir, output_file)

        assert file_count == 3
        with zipfile.ZipFile(output_file) as zf:
            for modid in ["mod_a", "mod_b", "mod_c"]:
                assert f"assets/{modid}/lang/zh_cn.json" in zf.namelist()

    def test_pack_skips_empty(self, tmp_path: Path) -> None:
        """Empty translation files should be skipped."""
        input_dir = tmp_path / "translations"
        modid_dir = input_dir / "emptymod"
        modid_dir.mkdir(parents=True)
        (modid_dir / "en_us.json").write_text("{}", encoding="utf-8")

        output_file = tmp_path / "resourcepack.zip"
        file_count = pack_resourcepack(input_dir, output_file)

        assert file_count == 0

    def test_pack_custom_format(self, tmp_path: Path) -> None:
        """Test custom pack format and description."""
        input_dir = tmp_path / "translations"
        modid_dir = input_dir / "testmod"
        modid_dir.mkdir(parents=True)
        (modid_dir / "en_us.json").write_text(
            json.dumps({"key": "value"}), encoding="utf-8"
        )

        output_file = tmp_path / "resourcepack.zip"
        pack_resourcepack(
            input_dir,
            output_file,
            pack_format=15,
            description="Custom pack",
        )

        with zipfile.ZipFile(output_file) as zf:
            meta = json.loads(zf.read("pack.mcmeta"))
            assert meta["pack"]["pack_format"] == 15
            assert meta["pack"]["description"] == "Custom pack"

    def test_pack_missing_input_dir(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for missing input directory."""
        with pytest.raises(FileNotFoundError):
            pack_resourcepack(tmp_path / "nonexistent", tmp_path / "out.zip")
