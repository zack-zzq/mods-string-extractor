# Mods String Extractor

[![PyPI version](https://badge.fury.io/py/mods-string-extractor.svg)](https://pypi.org/project/mods-string-extractor/)

从 Minecraft modpack 的 mods 中提取待翻译字符串，并在翻译完成后一键打包成资源包。

## 功能

- 🔍 **自动扫描** mods 目录下所有 `.jar` 文件
- 🌐 **智能提取** 待翻译字符串：
  - 如果 mod 已有 `zh_cn.json`，只提取 `en_us.json` 与 `zh_cn.json` 的差集
  - 如果 mod 没有 `zh_cn.json`，全量提取 `en_us.json`
- 📦 **一键打包** 翻译好的字符串为 Minecraft 资源包

## 安装

```bash
pip install mods-string-extractor
```

或使用 uv：

```bash
uv tool install mods-string-extractor
```

## 使用方法

### 1. 提取待翻译字符串

```bash
mods-string-extractor extract --mods /path/to/mods --output ./extracted
```

提取后的文件结构：

```
extracted/
├── ae2/
│   └── en_us.json
├── create/
│   └── en_us.json
├── mekanism/
│   └── en_us.json
└── ...
```

### 2. 翻译

编辑 `extracted/` 中的 `en_us.json` 文件，将英文值替换为中文翻译。

### 3. 打包资源包

```bash
mods-string-extractor pack --input ./extracted --output translation_pack.zip
```

可选参数：

```bash
mods-string-extractor pack \
  --input ./extracted \
  --output translation_pack.zip \
  --pack-format 34 \
  --description "My Translation Pack"
```

### 4. 使用资源包

将生成的 `.zip` 文件放入 Minecraft 的 `resourcepacks` 目录即可。

## 开发

```bash
# 克隆项目
git clone https://github.com/zack-zzq/mods-string-extractor.git
cd mods-string-extractor

# 安装开发依赖
uv sync

# 运行测试
uv run pytest tests/ -v
```

## License

MIT
