"""Tests for pam.py, run against a scratch root (never the host's PAM).

    python3 -I -m unittest discover -s dist -p '*_test.py'
"""

import os
import subprocess
import sys
import tempfile
import unittest

PAM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pam.py")
SUDO = "#%PAM-1.0\nauth include system-auth\naccount include system-auth\n"


def run(root: str, action: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-I", PAM, action, "--root", root],
        capture_output=True,
        text=True,
        check=True,
    )


class PamTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, "etc/pam.d"))

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, rel: str) -> str:
        return os.path.join(self.root, rel)

    def write(self, rel: str, text: str, mode: int = 0o644):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w") as f:
            f.write(text)
        os.chmod(self.path(rel), mode)

    def read(self, rel: str) -> str:
        with open(self.path(rel)) as f:
            return f.read()

    def test_block_fails_open(self):
        self.write("etc/pam.d/sudo", SUDO)
        run(self.root, "apply")
        lines = self.read("etc/pam.d/sudo").splitlines()
        self.assertEqual(lines[0], "#%PAM-1.0", "the header stays first")
        for stage in ("auth", "account"):
            i = next(
                n for n, l in enumerate(lines) if l.startswith(stage) and "pam_exec" in l
            )
            # Only a clean exit 0 from the gate falls through to pam_deny;
            # every other result (crash, missing binary, timeout) skips it.
            self.assertIn("[success=ignore default=1]", lines[i])
            self.assertRegex(lines[i + 1], rf"^{stage}\s+requisite pam_deny\.so$")
        self.assertLess(
            max(n for n, l in enumerate(lines) if "deepwork" in l),
            lines.index("auth include system-auth"),
            "the gate comes before every other rule",
        )

    def test_apply_twice_then_remove_restores(self):
        self.write("etc/pam.d/sudo", SUDO, 0o640)
        run(self.root, "apply")
        once = self.read("etc/pam.d/sudo")
        run(self.root, "apply")
        self.assertEqual(self.read("etc/pam.d/sudo"), once)
        self.assertEqual(os.stat(self.path("etc/pam.d/sudo")).st_mode & 0o7777, 0o640)
        run(self.root, "remove")
        self.assertEqual(self.read("etc/pam.d/sudo"), SUDO)

    def test_vendor_file_gets_a_copy_that_is_removed_again(self):
        self.write("usr/lib/pam.d/su", SUDO)
        run(self.root, "apply")
        self.assertIn("deepwork-pam-gate", self.read("etc/pam.d/su"))
        self.assertEqual(self.read("usr/lib/pam.d/su"), SUDO, "vendor file untouched")
        run(self.root, "remove")
        self.assertFalse(os.path.exists(self.path("etc/pam.d/su")))

    def test_missing_services_are_left_alone(self):
        run(self.root, "apply")
        self.assertEqual(os.listdir(self.path("etc/pam.d")), [])


if __name__ == "__main__":
    unittest.main()
