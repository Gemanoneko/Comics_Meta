import importlib.metadata
import re
import unittest
from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parents[1] / 'requirements.txt'
PIN = re.compile(r'([A-Za-z0-9][A-Za-z0-9._-]*)==([0-9][0-9A-Za-z.+!-]*)')


def normal(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def parse(text):
    result = {}
    for line in text.splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        match = PIN.fullmatch(line)
        if not match:
            raise ValueError('Not an exact pin: ' + line)
        result[normal(match[1])] = match[2]
    return result


def pins():
    return parse(REQUIREMENTS.read_text(encoding='utf-8'))


class RequirementsTests(unittest.TestCase):
    def test_every_line_is_an_exact_pin_and_direct_imports_are_pinned(self):
        self.assertLessEqual({'pillow', 'playwright'}, set(pins()))
        for loose in ('Pillow>=10', 'playwright>=1.55,<2', 'greenlet', 'pyee~=13.0'):
            with self.subTest(line=loose), self.assertRaises(ValueError):
                parse(loose)

    def test_every_runtime_dependency_of_a_pin_is_pinned(self):
        pinned = pins()
        checked = 0
        for name in pinned:
            for requirement in importlib.metadata.requires(name) or []:
                if re.search(r'''extra\s*==''', requirement):
                    continue  # Optional extras are not installed.
                dependency = normal(re.match(r'[A-Za-z0-9._-]+', requirement)[0])
                checked += 1
                with self.subTest(package=name, dependency=dependency):
                    self.assertIn(dependency, pinned)
        self.assertGreater(checked, 0)  # playwright alone has runtime dependencies.

    def test_installed_versions_match_the_pins(self):
        for name, version in pins().items():
            with self.subTest(package=name):
                self.assertEqual(importlib.metadata.version(name), version)
