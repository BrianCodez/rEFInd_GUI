#!/usr/bin/python3
"""Unprivileged, process-scoped Install Config hook for rEFInd_GUI 3.4.6."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
ORIGINAL_PATH = "REFIND_GUI_AUTOMATION_ORIGINAL_PATH"


def load_profile():
    profile = json.loads((ROOT / "profile.json").read_text())
    if profile["schema"] != 1:
        raise ValueError("Unsupported automation profile.")
    return profile


def verify_installation(profile):
    for label in ("gui", "helper"):
        actual = hashlib.sha256(Path(profile[f"{label}_executable"]).read_bytes()).hexdigest()
        if actual != profile[f"{label}_sha256"]:
            raise ValueError("rEFInd_GUI or its helper has changed after setup. "
                             "Review this automation before installing another config.")


def clean_environment(environment):
    result = dict(environment)
    original = result.pop(ORIGINAL_PATH, None)
    if original is not None:
        result["PATH"] = original
    return result


def windows_config(text, firmware, profile):
    """Pure transformation; select the current active entry for the correct ESP."""
    guid = profile["windows_esp_guid"]
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", guid):
        raise ValueError("Invalid Windows ESP identifier in the profile.")
    candidates = []
    expression = (r"^Boot([0-9A-Fa-f]{4})\*[^\n]*HD\(\d+,GPT,"
                  + re.escape(guid) + r",[^)]*\)/(?:File\()?"
                  + r"\\EFI\\Microsoft\\Boot\\bootmgfw\.efi")
    for entry in re.finditer(expression, firmware, re.MULTILINE | re.IGNORECASE):
        candidates.append(entry.group(1).upper())
    if not candidates:
        raise ValueError("No active Windows Boot Manager entry matches your Windows SSD. "
                         "Config installation stopped for review.")
    order = re.search(r"^BootOrder:\s*([0-9A-Fa-f,]+)", firmware, re.MULTILINE)
    bootnum = next((n.upper() for n in order.group(1).split(",") if n.upper() in candidates),
                   candidates[0]) if order else candidates[0]
    matches = list(re.finditer(r'^menuentry "Windows" \{[^{}]*\}', text, re.MULTILINE))
    if len(matches) != 1:
        raise ValueError("Expected one Windows menu entry. Review the GUI selections before installing.")
    match = matches[0]
    stanza = match.group()
    icons = re.findall(r"^\s*icon\s+(/EFI/refind/os_icon[1-4]\.png)\s*$", stanza, re.MULTILINE)
    if len(icons) != 1:
        raise ValueError("Unexpected Windows icon path; config installation stopped.")
    if re.search(r"^\s*loader\s+", stanza, re.MULTILINE):
        volume = re.search(r'^\s*volume\s+"([^"]+)"\s*$', stanza, re.MULTILINE)
        loader = re.search(r"^\s*loader\s+(\S+)\s*$", stanza, re.MULTILINE)
        if (not volume or volume.group(1).lower() != guid.lower() or not loader
                or loader.group(1).lower() != "/efi/microsoft/boot/bootmgfw.efi"):
            raise ValueError("Selected Windows entry does not match your Windows SSD. Installation stopped.")
    elif not re.search(r"^\s*firmware_bootnum\s+[0-9A-Fa-f]{4}\s*$", stanza, re.MULTILINE):
        raise ValueError("Unexpected Windows launch settings; config installation stopped.")
    replacement = ('menuentry "Windows" {\n' + f'\ticon {icons[0]}\n'
                   + f'\tfirmware_bootnum {bootnum}\n' + "}")
    return text[:match.start()] + replacement + text[match.end():]


def preserve_windows(profile):
    target = Path.home() / profile["gui_data_relative"] / "refind.conf"
    if target.is_symlink() or not target.is_file():
        raise ValueError("Expected a regular GUI config; installation stopped.")
    original = target.read_bytes()
    firmware = subprocess.run(["/usr/bin/efibootmgr", "-v"], check=True,
                              capture_output=True, text=True,
                              env=clean_environment(os.environ)).stdout
    updated = windows_config(original.decode("utf-8"), firmware, profile).encode("utf-8")
    if original == updated:
        return
    backups = Path.home() / profile["state_relative"] / "backups"
    backups.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, backup = tempfile.mkstemp(prefix="before-windows-preserve-", suffix=".conf", dir=backups)
    with os.fdopen(fd, "wb") as out:
        out.write(original)
    fd, stage = tempfile.mkstemp(prefix=".refind-preserve-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(updated)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(stage, target.stat().st_mode & 0o777)
        if target.read_bytes() != original:
            raise ValueError("GUI config changed during installation; finish Create Config and retry Install Config.")
        os.replace(stage, target)
    finally:
        if os.path.exists(stage):
            os.unlink(stage)


def sudo_hook(arguments, profile):
    expected = ["-n", profile["helper_executable"], "install-config"]
    if arguments == expected:
        verify_installation(profile)
        preserve_windows(profile)
        print("Windows firmware launch setting preserved automatically.", flush=True)
    # The customization never becomes root. The original sudo policy and
    # root-owned helper handle privilege as before, with the original PATH.
    os.execve("/usr/bin/sudo", ["/usr/bin/sudo", *arguments], clean_environment(os.environ))


def launch(profile):
    verify_installation(profile)
    environment = clean_environment(os.environ)
    original = environment.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    environment[ORIGINAL_PATH] = original
    environment["PATH"] = str(ROOT / "bin") + ":" + original
    os.execve(profile["gui_executable"], [profile["gui_executable"]], environment)


def main():
    profile = load_profile()
    if os.getuid() == 0:
        raise ValueError("This customization runs as your normal user, not with sudo.")
    if sys.argv[1:] == ["--verify"]:
        verify_installation(profile)
        print("Installed GUI/helper hashes match the reviewed version.")
    elif sys.argv[1:] == ["--launch"]:
        launch(profile)
    elif sys.argv[1:2] == ["--sudo-hook"]:
        sudo_hook(sys.argv[2:], profile)
    else:
        raise ValueError("Use --launch or --verify.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        message = f"rEFInd GUI automation stopped: {error}"
        print(message, file=sys.stderr)
        if sys.argv[1:] == ["--launch"]:
            subprocess.run(["/usr/bin/zenity", "--error", "--title=rEFInd GUI",
                            "--text=" + message], check=False)
        sys.exit(1)
