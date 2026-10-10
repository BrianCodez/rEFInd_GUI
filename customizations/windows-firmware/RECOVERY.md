# Reusing this customization

This folder backs up the GUI customization, not an entire boot installation.
It targets the reviewed rEFInd_GUI 3.4.6 Linux GUI/helper pair. The exact
hashes and Windows ESP identity are recorded in profile.json. A new package,
disk layout, or OS requires reviewing those values before use.

## Restore the GUI integration on the same installation

Close all rEFInd_GUI windows. Confirm the binaries match profile.json:

```sh
sha256sum /etc/rEFInd/rEFInd_GUI /etc/rEFInd/rEFInd_GUI_helper
efibootmgr -v
```

The Windows entry must target the Windows ESP recorded in profile.json and
`\EFI\Microsoft\Boot\bootmgfw.efi`. This integration requires Python 3,
efibootmgr, and the original GUI's approved Install Config helper setup.

From this folder, copy only the source files to the user runtime:

```sh
install -d -m 700 "$HOME/.local/lib/refind-gui-automatic/bin"
install -m 600 integration.py profile.json "$HOME/.local/lib/refind-gui-automatic/"
install -m 700 bin/sudo "$HOME/.local/lib/refind-gui-automatic/bin/sudo"
```

Back up any existing user launcher before editing it. Copy the system
`/usr/share/applications/rEFInd_GUI.desktop` into
`~/.local/share/applications/rEFInd_GUI.desktop` and change only its Exec
line to the following, substituting the actual absolute home path:

```ini
Exec=/usr/bin/python3 /home/brian/.local/lib/refind-gui-automatic/integration.py --launch
```

If using a Desktop shortcut, back it up and apply the same Exec line there.
Do not run the integration as root. Reopen the app through the updated
launcher, choose images, Create Config, then Install Config. The hook should
report that it preserved the Windows firmware launch entry. Check that
the installed Windows stanza uses `firmware_bootnum` before rebooting.

Rollback of this user integration: restore the saved Desktop shortcut and
restore/remove the user app-menu override as appropriate. This does not
undo the live EFI config. Avoid restoring a direct Windows chainload stanza
on this machine: it failed during the earlier boot test.

## Boot setup record for Brian's PC

MSI PRO B650-P WIFI; Fedora on SPCC 4TB, Windows on Samsung 970 EVO Plus 1TB.
Device names and Boot numbers below are observations from setup, not stable
identifiers for a future installation. Recheck them before any command.

| Item | Observed identity / path |
| --- | --- |
| Fedora ESP | `2d2849d3-c328-410c-a1e4-3dda14cf3536` |
| Windows ESP | `c0c58765-a095-452a-87d2-76c8a5888393` |
| rEFInd entry | Boot0001, `\EFI\refind\shimx64.efi` on Fedora ESP |
| Fedora entry | Boot0005, `\EFI\fedora\shimx64.efi` |
| Windows entry | Boot0002, `\EFI\Microsoft\Boot\bootmgfw.efi` on Samsung |

The separate `EFI/refind` directory contains Fedora's signed shim and
MokManager, locally signed rEFInd as `grubx64.efi` (shim's next stage), and a
matching `refind_x64.efi` alias for GUI detection. The original Fedora and
Windows bootloader files remain separate. The public MOK certificate is
enrolled; the signing private key is stored locally with root-only access.
Secure Boot remained enabled. **Do not use the GUI Install rEFInd button**
on this layout: it can replace the specially signed loader arrangement.
Use Install Config for appearance changes.

Fedora's GUI menu entry loads `\EFI\fedora\shimx64.efi` on the Fedora ESP.
Windows uses `firmware_bootnum` for its native firmware entry. This Windows
method can involve a restart before Windows loads.

Desired firmware order: rEFInd, Fedora, then the existing Windows entries.
The observed target was `0001,0005,0002,0003`. A pending BootNext can override
that for one boot. On this MSI board the per-loader order is under Advanced
Settings > Boot > UEFI Hard Disk Drive BBS Priorities, rather than the
general device-category icons. Do not delete other boot entries to set it.
At backup preparation, a read-only check showed BootCurrent 0001 and order
`0001,0005,0003,0002`: rEFInd first, Fedora second. Boot0002 was present but
inactive (no asterisk), while Boot0003 was active. The integration requires
an active entry matching the recorded Windows ESP, so another Install Config
will stop until that situation is reviewed. No firmware repair was performed
as part of saving this source backup.

For recovery, use MSI F11 and select the existing Fedora or Windows entry.
If restoring permanent priority, inspect `efibootmgr -v` first, then use
the verified entry numbers in `sudo efibootmgr --bootorder ...`. This is a
firmware change and is intentionally not performed by the GUI integration.
Keeping those original entries provides an independent way to boot.

The original EFI archive and saved configs are local under
`/home/brian/Documents/Codex/2026-10-10/im/outputs/refind-backup`.
They are not included in this GitHub source backup. The signing material is
local under `/etc/refind.d/keys/refind-spcc`; never upload its private key.
For a fresh installation, obtain current trusted shim/rEFInd packages,
check signatures and revocation compatibility, sign the new loader with a
protected key, enroll its public certificate through MokManager, and test
the separate boot entry before changing default priority. The GitHub fork
preserves the design and integration code; it does not eliminate those
machine-specific Secure Boot steps.
