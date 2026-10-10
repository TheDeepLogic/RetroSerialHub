import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from rsh_welcome import load_banner, reset_banner, save_banner, validate_banner


class WelcomeBannerTests(unittest.TestCase):
    def test_configured_banner_is_used_without_saved_override(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "welcome_banner.json"
            self.assertEqual(load_banner("Configured", path), "Configured")

    def test_saved_banner_overrides_config_and_persists(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "welcome_banner.json"
            save_banner(path, "My Retro BBS")

            self.assertEqual(load_banner("Configured", path), "My Retro BBS")
            self.assertEqual(json.loads(path.read_text())["banner"], "My Retro BBS")

    def test_reset_removes_override_and_restores_configured_banner(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "welcome_banner.json"
            save_banner(path, "My Retro BBS")
            reset_banner(path)

            self.assertEqual(load_banner("Configured", path), "Configured")
            self.assertFalse(path.exists())

    def test_banner_validation_rejects_empty_overlong_and_control_text(self):
        with self.assertRaises(ValueError):
            validate_banner("")
        with self.assertRaises(ValueError):
            validate_banner("x" * 81)
        with self.assertRaises(ValueError):
            validate_banner("Bad\nBanner")
        self.assertEqual(validate_banner("  Valid Banner  "), "Valid Banner")


if __name__ == "__main__":
    unittest.main()
