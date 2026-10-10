# rEFInd_GUI automatic Windows firmware entry

Local customization for the reviewed Fedora rEFInd_GUI 3.4.6 package.
It preserves the Windows firmware launch method when Install Config is
clicked. Use the normal app-menu launcher or the updated Desktop shortcut:
choose images, Create Config, Install Config. No terminal command per edit.
Brian reported that Windows booted with the firmware launch method. This
does not establish that every later GUI edit has used this launcher hook;
verify one fresh GUI Install Config operation and the resulting config.

The original GUI and privileged helper are unchanged. This launcher sets
a private PATH only for the GUI process. Its private `sudo` command restores
the Windows stanza as the normal user immediately before the exact native
Install Config request, then invokes the original /usr/bin/sudo with the
original PATH. All other sudo requests are forwarded without config edits.
No new sudo rule, root program, system service, autostart, or scheduled job
is installed. No EFI executable, firmware entry or Secure Boot key is
modified by the automation itself. The existing Install Config helper
continues to publish the config and images to the ESP.

The Windows icon stays the one currently selected in the GUI. The Windows
ESP GUID is in profile.json, and the current active matching boot number is
resolved from efibootmgr each time. Existing settings outside the Windows
stanza are preserved byte-for-byte. Each changed staged config is backed up
under ~/.local/state/refind-gui-automatic/backups. Unexpected GUI configs or
missing/mismatched Windows entries stop the install before privilege.

The launcher and Install Config hook check the installed GUI/helper hashes.
After an app update changes those binaries, this launcher refuses to run
until the new code and helper invocation are reviewed and profile hashes
updated. Do not simply replace hashes without checking compatibility.
Directly launching /etc/rEFInd/rEFInd_GUI bypasses the customization; use
the app-menu entry or Desktop shortcut. Already-open windows must be closed
and reopened once after setup to receive the hook.

Runtime: ~/.local/lib/refind-gui-automatic/.
Launcher override: ~/.local/share/applications/rEFInd_GUI.desktop.
Desktop shortcut: ~/Desktop/refind_GUI.desktop (if it already exists).
Setup receipt and original launchers are kept beside this source backup in
../refind-gui-automation-backup/.

## Portability and source backup

These files are versioned in a local Git repository, with a Git bundle
backup beside it. This is a customization layer, not a fork of the GUI
binary or a replacement for the separate shim/MOK installation backup.
In a fork, keep this layer under `customizations/windows-firmware/` so it
does not replace upstream code. No signing private keys are included.
See RECOVERY.md for reinstall guidance and the separate boot setup record.
See [SECURE_BOOT_METHODS.md](SECURE_BOOT_METHODS.md) for the trust chain,
installation history, Windows workaround, alternatives and their tradeoffs.

On another Linux OS, install and review rEFInd_GUI and its normal privileged
helper first. Confirm shim/MOK booting, Secure Boot and the Windows firmware
entry independently. Set the correct Windows ESP GUID, paths and reviewed
binary hashes in profile.json. Paths to user settings resolve from the
current account's home directory; no username is embedded in the code.
Windows itself does not use this Linux launcher integration.

Run the nine integration checks with `python3 tests/test_integration.py`.
They use recorded/config fixtures and temporary directories; they do not
read or modify live EFI files or firmware. Passing these checks does not
establish that the current Windows firmware entry is active; see RECOVERY.md.

## Rollback (when requested)

Restore the original Desktop shortcut from the setup backup and remove the
user app-menu override to use the original system launcher again. For an
appearance rollback, use a reviewed saved config that retains the Windows
method; the old direct-chainload config failed its boot test.
Removing the automation alone does not
change the live EFI config, Secure Boot or firmware entries.
