# Page

A simple encrypted notes manager for Windows.

## Features

- Store notes as age-encrypted JSON files
- Each note has a title, tags, and free-form text content
- Search by keyword, filter by tag
- Passphrase-based encryption — no keys to manage
- No cloud, no accounts, no telemetry — data stays local

## Requirements

- Python 3.11+
- [age](https://github.com/FiloSottile/age/releases) — download and place `age.exe` and `age-plugin-batchpass.exe` in the project directory

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

- **New Entry**: create a note
- **Apply**: save edits to the current note
- **Cancel**: discard edits
- **File → Save**: encrypt and save to a `.page` file
- **File → Open**: open and decrypt a `.page` file

## File Format

Notes are stored as JSON, encrypted with [age](https://age-encryption.org) using passphrase mode (scrypt). Files use the `.page` extension.

## License

All rights reserved.
