"""
crypto.py - age encryption/decryption wrapper

Dependencies:
    age.exe and age-plugin-batchpass.exe must be in the same directory
    as this script or the PyInstaller bundle.

Flow:
    Encrypt: plaintext bytes -> zstd compress -> age encrypt (armor) -> str
    Decrypt: str -> normalize line endings -> age decrypt -> zstd decompress -> plaintext bytes

Passphrase is passed via AGE_PASSPHRASE environment variable.
No console window is created on Windows.
No temporary files are used.
"""

import os
import sys
import subprocess
import zstandard as zstd


def _age_dir() -> str:
    """Return directory containing age.exe and age-plugin-batchpass.exe."""
    if getattr(sys, 'frozen', False):
        # PyInstaller bundle: executables are in _MEIPASS
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))


def _run(args: list[str], stdin_data: bytes, passphrase: str) -> bytes:
    """
    Run age.exe with given args, feeding stdin_data.
    Passphrase is passed via AGE_PASSPHRASE environment variable.
    age-plugin-batchpass.exe is found via PATH injection.
    No console window is created on Windows.
    Returns stdout on success. Raises RuntimeError on failure.
    """
    age_dir = _age_dir()
    age_exe = os.path.join(age_dir, 'age.exe')

    # Inject age_dir into PATH so age.exe can find age-plugin-batchpass.exe
    env = os.environ.copy()
    env['PATH'] = age_dir + os.pathsep + env.get('PATH', '')
    env['AGE_PASSPHRASE'] = passphrase

    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0

    proc = subprocess.run(
        [age_exe] + args,
        input=stdin_data,
        capture_output=True,
        env=env,
        creationflags=creation_flags,
    )

    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors='replace').strip())

    return proc.stdout


def encrypt(plaintext: bytes, passphrase: str) -> str:
    """
    Compress and encrypt plaintext bytes with the given passphrase.
    Returns armor-encoded ciphertext as a str.
    Raises RuntimeError on failure.
    """
    # Step 1: compress
    cctx = zstd.ZstdCompressor(level=3)
    compressed = cctx.compress(plaintext)

    # Step 2: encrypt with age + batchpass plugin, armor output
    ciphertext = _run(
        ['-e', '-j', 'batchpass', '-a'],
        stdin_data=compressed,
        passphrase=passphrase,
    )

    return ciphertext.decode('ascii')


def decrypt(armor_text: str, passphrase: str) -> bytes:
    """
    Decrypt armor-encoded ciphertext with the given passphrase.
    Returns decompressed plaintext bytes.
    Raises RuntimeError on wrong passphrase or corrupt data.
    """
    # Step 1: normalize line endings before passing to age
    normalized = armor_text.replace('\r\n', '\n').encode('ascii')

    # Step 2: decrypt
    compressed = _run(
        ['-d', '-j', 'batchpass'],
        stdin_data=normalized,
        passphrase=passphrase,
    )

    # Step 3: decompress
    dctx = zstd.ZstdDecompressor()
    try:
        return dctx.decompress(compressed)
    except zstd.ZstdError as e:
        raise RuntimeError(f"Decompression failed: {e}")
