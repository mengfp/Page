"""
crypto.py - age encryption/decryption wrapper

Dependencies:
    age.exe and age-plugin-batchpass.exe must sit next to the app
    (project root when dev; same folder as Page.exe when shipped as a directory / PyInstaller onedir).

Flow:
    Encrypt: plaintext bytes -> age encrypt (armor) -> str
    Decrypt: str -> normalize line endings -> age decrypt -> plaintext bytes

Passphrase is passed via AGE_PASSPHRASE environment variable.
No console window is created on Windows.
No temporary files are used.
"""

import os
import sys
import subprocess


def _age_dir() -> str:
    """Return directory containing age.exe and age-plugin-batchpass.exe."""
    if getattr(sys, 'frozen', False):
        # PyInstaller onedir: runtime root (age exes bundled there; avoid onefile)
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))


def age_bundle_ready() -> bool:
    """True if age.exe and age-plugin-batchpass.exe exist next to app / in bundle."""
    d = _age_dir()
    return os.path.isfile(os.path.join(d, "age.exe")) and os.path.isfile(
        os.path.join(d, "age-plugin-batchpass.exe")
    )


def age_bundle_help_text() -> str:
    d = _age_dir()
    return (
        f"Expected in:\n{d}\n\n"
        "- age.exe\n"
        "- age-plugin-batchpass.exe\n\n"
        "Same folder as Page (dev) or inside the app bundle (release)."
    )


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
    Encrypt plaintext bytes with the given passphrase (no compression).
    Returns armor-encoded ciphertext as a str.
    Raises RuntimeError on failure.
    """
    ciphertext = _run(
        ['-e', '-j', 'batchpass', '-a'],
        stdin_data=plaintext,
        passphrase=passphrase,
    )
    return ciphertext.decode('ascii')


def decrypt(armor_text: str, passphrase: str) -> bytes:
    """
    Decrypt armor-encoded ciphertext with the given passphrase.
    Returns plaintext bytes (e.g. UTF-8 JSON).
    Raises RuntimeError on wrong passphrase or corrupt data.
    """
    normalized = armor_text.replace('\r\n', '\n').encode('ascii')
    return _run(
        ['-d', '-j', 'batchpass'],
        stdin_data=normalized,
        passphrase=passphrase,
    )
