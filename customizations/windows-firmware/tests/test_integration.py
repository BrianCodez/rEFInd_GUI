import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('integration', root / 'integration.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
profile = json.loads((root / 'profile.json').read_text())
config = (root / 'tests/input.conf').read_text()
expected = (root / 'tests/expected.conf').read_text()
firmware = (root / 'tests/firmware.txt').read_text()

class SafetyChecks(unittest.TestCase):
    def test_actual_generated_config_matches_approved_change(self):
        self.assertEqual(module.windows_config(config, firmware, profile), expected)
        self.assertEqual(module.windows_config(expected, firmware, profile), expected)

    def test_new_icon_and_changed_boot_number_are_preserved(self):
        new_config = config.replace('icon /EFI/refind/os_icon2.png', 'icon /EFI/refind/os_icon4.png')
        new_firmware = firmware.replace('Boot0002*', 'Boot00AB*').replace('BootOrder: 0002', 'BootOrder: 00AB')
        result = module.windows_config(new_config, new_firmware, profile)
        self.assertIn('firmware_bootnum 00AB', result)
        self.assertIn('icon /EFI/refind/os_icon4.png', result)
        self.assertEqual(result.split('menuentry "Windows"')[0], new_config.split('menuentry "Windows"')[0])

    def test_wrong_selected_windows_ssd_is_rejected(self):
        with self.assertRaises(ValueError):
            module.windows_config(config.replace(profile['windows_esp_guid'], 'a4a20027-a285-4055-be98-451d6ebb087a'), firmware, profile)

    def test_missing_active_windows_entry_is_rejected(self):
        with self.assertRaises(ValueError):
            module.windows_config(config, firmware.replace('Boot0002*', 'Boot0002 '), profile)

    def test_other_privileged_request_is_forwarded_without_edits(self):
        args = ['-n', profile['helper_executable'], 'install-themes']
        with patch.object(module, 'preserve_windows') as preserve, patch.object(module, 'verify_installation') as verify, patch.object(module.os, 'execve') as execute:
            module.sudo_hook(args, profile)
            preserve.assert_not_called()
            verify.assert_not_called()
            self.assertEqual(execute.call_args.args[:2], ('/usr/bin/sudo', ['/usr/bin/sudo', *args]))

    def test_installation_failure_never_invokes_sudo(self):
        args = ['-n', profile['helper_executable'], 'install-config']
        with patch.object(module, 'verify_installation', side_effect=ValueError('updated app')), patch.object(module, 'preserve_windows') as preserve, patch.object(module.os, 'execve') as execute:
            with self.assertRaises(ValueError):
                module.sudo_hook(args, profile)
            preserve.assert_not_called()
            execute.assert_not_called()

    def test_config_failure_never_invokes_sudo(self):
        args = ['-n', profile['helper_executable'], 'install-config']
        with patch.object(module, 'verify_installation'), patch.object(module, 'preserve_windows', side_effect=ValueError('wrong SSD')), patch.object(module.os, 'execve') as execute:
            with self.assertRaises(ValueError):
                module.sudo_hook(args, profile)
            execute.assert_not_called()

    def test_user_config_write_and_backup_in_temporary_home(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            target = home / profile['gui_data_relative'] / 'refind.conf'
            target.parent.mkdir(parents=True)
            target.write_text(config)
            result = subprocess.CompletedProcess([], 0, stdout=firmware, stderr='')
            with patch.object(module.Path, 'home', return_value=home), patch.object(module.subprocess, 'run', return_value=result):
                module.preserve_windows(profile)
                self.assertEqual(target.read_text(), expected)
                backups = list((home / profile['state_relative'] / 'backups').glob('*.conf'))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_text(), config)
                module.preserve_windows(profile)
                self.assertEqual(len(list(backups[0].parent.glob('*.conf'))), 1)

    def test_launcher_only_scopes_path_to_child_and_restores_it_for_sudo(self):
        original = os.environ.get('PATH', '')
        with patch.object(module, 'verify_installation'), patch.object(module.os, 'execve') as execute:
            module.launch(profile)
            app, args, environment = execute.call_args.args
            self.assertEqual(app, profile['gui_executable'])
            self.assertEqual(os.environ.get('PATH', ''), original)
            self.assertEqual(environment[module.ORIGINAL_PATH], original)
            self.assertEqual(module.clean_environment(environment)['PATH'], original)
            self.assertNotIn(module.ORIGINAL_PATH, module.clean_environment(environment))

if __name__ == '__main__':
    unittest.main()
