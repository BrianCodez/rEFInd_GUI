# How we used rEFInd with Secure Boot, and why

Recorded October 10, 2026. This explains our Fedora / Windows design and
alternatives for a future installation. Machine-specific boot identifiers,
certificate subjects, signing-key locations and user filesystem paths are
omitted. Examples use standard EFI filenames or placeholders. Keep private
signing material and detailed machine records separately.

See [README.md](README.md) for the Linux GUI integration and
[RECOVERY.md](RECOVERY.md) for the existing recovery notes.

## The goal and three separate problems

We wanted a customizable rEFInd menu for Fedora and Windows on separate
SSDs, with Secure Boot enabled and the original OS boot paths retained.
Appearance changes through rEFInd_GUI should retain our Windows workaround.

Firmware priority chooses what starts first. Secure Boot trust decides
whether boot code may run. rEFInd configuration decides what its menu shows
and launches. Fixing one does not automatically fix the others. The GUI
runs inside Linux to edit files; rEFInd runs before the OS starts.

## Our trust method: Fedora shim and a local MOK

We reused Fedora's trusted, Microsoft-signed **shim**, a small first-stage
loader. Its **MOK** (Machine Owner Key) mechanism lets the owner authorize
an additional signer through shim without replacing motherboard Secure Boot
keys. Firmware trust and shim's MOK list are different stores. Enrolling a
MOK does not by itself make firmware trust our signed rEFInd directly;
our firmware entry therefore launches shim first.
[Fedora Secure Boot overview](https://fedoraproject.org/wiki/Secureboot)

The design uses a separate directory on the Linux EFI system partition
(ESP). These are standard EFI filenames, not machine-specific identifiers:

| File | Role |
| --- | --- |
| `shimx64.efi` | Copy of Fedora's signed shim; target of our firmware entry |
| `mmx64.efi` | Matching MokManager for enrollment requests |
| `grubx64.efi` in the rEFInd directory | Locally signed **rEFInd**, renamed for shim's next-stage filename |
| `refind_x64.efi` in the same directory | Matching rEFInd copy for GUI detection |
| `refind.conf`, PNG assets and icons | Menu content and appearance |

Renaming rEFInd does not replace Fedora's real GRUB in its own directory.
Keeping shim, MokManager and the renamed loader together follows the rEFInd
author's documented approach.
[rEFInd Secure Boot guide](https://www.rodsbooks.com/refind/secureboot.html)

```text
UEFI firmware
  -> trusted Fedora shim in the separate rEFInd directory
  -> locally signed rEFInd, accepted using our enrolled MOK
  -> rEFInd's Fedora selection
  -> original Fedora shim
  -> original Fedora GRUB
  -> Fedora's distribution-signed kernel
```

We retained Fedora's normal kernel boot chain instead of making rEFInd
launch arbitrary kernels directly. Stock Fedora updates can continue using
Fedora's signing/bootloader management. Custom kernels and third-party
modules still need their own trust review.
[Fedora signing model](https://fedoraproject.org/wiki/Secureboot)

### What we did and why

1. **Inspected the existing setup.** Established the OS/ESP identities,
   examined firmware entries and signatures, reviewed the GUI installation,
   and confirmed both OSs already booted independently.
2. **Saved the working state.** Backed up EFI files, firmware records and
   hashes. Preparation checks stopped on unexpected identities or an
   existing target instead of overwriting it.
3. **Reviewed and signed rEFInd.** Used a reviewed upstream GNU-EFI build,
   generated a protected local key/certificate, signed with `sbsign`, and
   checked with `sbverify`. Signing authorizes code; it does not establish
   that the code is safe, so provenance review comes first.
4. **Added a separate shim/rEFInd entry.** Preserved the original Fedora and
   Windows paths. Initially left permanent priority unchanged for testing.
5. **Enrolled the public certificate through MokManager.** `mokutil --import`
   queued the request; the owner confirmed it at boot using a chosen temporary
   password. This authorizes the request, not every subsequent boot.
6. **Checked enrollment and actual booting.** We obtained an enrolled-key
   result, Secure Boot enabled, and a Fedora session reported after choosing
   it in rEFInd.
7. **Installed appearance data.** Added standard icons and used the existing
   GUI's Create Config / Install Config workflow for selected images.
8. **Handled Windows launching and GUI regeneration separately**, as below.
9. **Adjusted default priority after testing.** rEFInd first, Fedora next,
   with existing Windows entries retained. One-time overrides and firmware
   per-loader priority also needed inspection.

We did not reset motherboard keys, re-sign Windows Boot Manager, replace
Fedora GRUB, or disable Secure Boot. No additional controller/touchscreen
EFI drivers were added to this manual layout.

Historical versions were rEFInd_GUI v3.4.6 and upstream rEFInd 0.14.2
GNU-EFI. These record what was reviewed, not versions to install forever.
A new installation needs current packages and policy reviewed again.

## Windows launching was a separate workaround

The GUI originally generated a direct Windows loader stanza. Selecting it
produced a gray screen and restart, followed by Windows booting through the
firmware default. No diagnostic established whether signatures, firmware,
graphics or another compatibility issue caused the failure. We did not
assume re-signing Microsoft's loader would fix it.

We replaced the Windows stanza's direct fields with `firmware_bootnum`,
keeping the selected icon. This schematic example uses placeholders:

```text
menuentry "Windows" {
    icon <SELECTED_ICON_PATH>
    firmware_bootnum <VERIFIED_WINDOWS_ENTRY_NUMBER>
}
```

Replace the placeholders before use. `firmware_bootnum` requests a one-time
firmware boot selection and restart into an existing entry. It is incompatible
with the previous `volume`/`loader` direct-chainload fields. It adds a handoff
while retaining the chosen menu icon.
[rEFInd firmware boot options](https://www.rodsbooks.com/refind/configfile.html#bootnext)

```text
rEFInd: select Windows
  -> one-time firmware Windows selection and restart
  -> native Windows Boot Manager
  -> Windows
```

Windows subsequently booted according to the user's report. An early test
also had Windows as the permanent default, so that report alone did not
conclusively establish that the selection caused the boot. Preserve that
distinction in future diagnosis. Microsoft's original loader can retain its
Microsoft signature when firmware trusts the signer. Our MOK authorizes
rEFInd, not a replacement Windows signing key.

### Why image edits needed a GUI integration

Create Config regenerates a direct Windows stanza. A later image edit and
regeneration could undo our workaround while Secure Boot trust stayed correct.

Our Linux launcher checks the reviewed GUI/helper hashes, resolves an active
Windows firmware entry matching the configured Windows ESP, and restores
only the Windows launch method just before the original Install Config
request. It retains the selected icon and settings outside that stanza.
It runs as the normal user, backs up the staged config, and delegates ESP
writing to the existing privileged helper. It adds no service or new sudo rule.

Use the updated launcher and reopen old GUI windows. Launching the original
GUI binary directly bypasses the integration. Package updates that change
pinned hashes intentionally stop it pending compatibility review.

**Install Config** publishes data files. **Install rEFInd** can replace EFI
programs and disrupt the signed arrangement. Use Install Config for appearance
changes. Images/config do not need the executable's EFI signature; replacing
an EFI program requires reviewing its trust again.

## Alternatives and their tradeoffs

This table is our assessment for this installation and its goals, not proof
one method is best everywhere or instructions to migrate now.

| Method | Advantages | Costs / why we did not choose it here |
| --- | --- | --- |
| **Our shim/MOK + rEFInd arrangement** | Preserves firmware trust and original OS paths; customized menu; independent OS entries remain | Maintain the separate shim copy and key; Windows handoff and GUI integration add complexity |
| **Upstream `refind-install --shim ... --localkeys`** | Automates much of the same shim/local signing design on a fresh installation | Still needs enrollment and reviewing script effects; does not inherently solve our Windows symptom or GUI regeneration |
| **Owner firmware keys using sbctl** | Can trust signed rEFInd directly; manages keys and tracks files needing signatures; useful with an OS already integrating it | Broader trust/update responsibility; the developer's reset/setup-mode recipe was more invasive than needed here |
| **Add our signer to firmware trust while retaining vendor keys** | Can remove the shim step and preserve vendor trust | Firmware enrollment support varies; still changes firmware trust and needs signing maintenance; not tested here |
| **Existing Fedora shim/GRUB with Windows entry and a theme** | Reuses Fedora's existing chain; graphical backgrounds/icons; likely fewer extra components for a basic menu here | Configure/test menu visibility, theme and Windows entry; different workflow from rEFInd_GUI; chainloading compatibility still needs testing |
| **systemd-boot with trusted loader/signed images** | Simple text menu; suits unified kernel images | Different boot/image layout and trust setup; not the requested themed menu; separate ESPs need planning |
| **Motherboard boot menu only** | Original working paths with no added manager | Requires invoking the firmware menu; limited appearance control |
| **rEFInd with Secure Boot disabled** | Avoids signing/enrollment work | Gives up required protection; may conflict with software requirements; does not inherently fix priority or chainloading |

The rEFInd installer documents `--shim` and `--localkeys`. It could reduce
bespoke preparation on a fresh installation, but should not be run over
this arrangement without checking its effects.
[rEFInd installation options](https://www.rodsbooks.com/refind/refind-install.html)

The GUI developer's sbctl guide clears existing firmware keys, creates
owner keys and enrolls with `--microsoft`. This is an alternative, not a
requirement for rEFInd. sbctl's manual also covers Microsoft/OEM certificate
options and Option ROM precautions. Retaining Microsoft trust can leave
Microsoft's Windows signatures usable; do not automatically re-sign Windows
files. The reset recipe is what we declined, not a claim every sbctl workflow
must discard all existing keys.
[Reviewed GUI guide](https://github.com/jlobue10/rEFInd_GUI/blob/11597b3630d777bca63cfa8923c9e71012ed542e/README.md#secure-boot-considerations),
[sbctl manual](https://github.com/Foxboron/sbctl/blob/master/docs/sbctl.8.txt)

GRUB supports graphical themes. For a basic attractive menu here, starting
with the existing Fedora GRUB would have been a reasonable simpler choice.
The extra work came from selecting the rEFInd GUI workflow, preserving
existing trust and handling the Windows symptom.
[GRUB theme manual](https://www.gnu.org/software/grub/manual/grub/html_node/Theme-file-format.html)

systemd-boot provides a text menu and generally expects images on its ESP
or an XBOOTLDR partition. It is a different installation design, rather
than a drop-in fix for this GUI setup.
[systemd-boot upstream manual](https://github.com/systemd/systemd/blob/main/man/systemd-boot.xml)

## Resuming, maintaining or changing methods

First inspect Secure Boot state, enrollment, partition identities, signatures,
current config and firmware entries/priority. `mokutil --sb-state`,
`efibootmgr -v` and `lsblk` inspect state. `mokutil --test-key` and
`sbverify --cert` can check the relevant local certificate/binary. Keep
machine-specific outputs in a private record. Boot numbers may change;
reinstallation can change partition GUIDs. A different OS can use different
GUI/helper paths and signing arrangements.

A listed signature does not alone prove current policy accepts a binary.
Actual boot tests matter. Our last observed Fedora session started through
rEFInd and its priority was first, but the expected Windows entry was
inactive. The hook stops another config install until that discrepancy is
reviewed. Nine fixture-based tests pass; they do not certify live boot state
or prove an actual GUI hook invocation. This update changes documentation only.

MOK enrollment adds trust for software signed with that private key. Protect
it and keep it out of GitHub. A clean installation needs either a separate
secure key backup or a new key/public-certificate enrollment. This repository
cannot recreate a lost private key.

Distribution updates maintain normal bootloader paths, not necessarily the
copied shim/MokManager beside rEFInd. Review those copies after security
updates. Firmware `dbx` and shim SBAT updates can reject old loaders despite
signatures; re-signing an obsolete binary is not a general revocation fix.
[Shim SBAT design](https://github.com/rhboot/shim/blob/main/SBAT.md)

Keep original OS files/entries while preparing an alternative. Use the
motherboard boot menu to select those paths independently if rEFInd fails.
A later entry in BootOrder is a fallback candidate, not a guarantee firmware
recovers from every hang.

For a move to GRUB, first boot the existing Fedora entry and test a visible
menu and both OS choices before changing permanent priority. For owner
firmware keys, first plan vendor trust, signing automation, updates and
recovery; that is broader than MOK enrollment. Retain applicable disk
encryption recovery credentials locally before changing boot/trust methods.

Retire the old integration only after a replacement passes real Fedora and
Windows boot tests with Secure Boot enabled. Making an existing OS entry
the default can be enough to stop using rEFInd; deleting files or revoking
its MOK is separate optional cleanup. Any migration/remediation needs the
owner's approval before implementation.
