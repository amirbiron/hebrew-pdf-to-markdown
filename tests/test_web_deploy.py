"""הפריסה והגבולות בין החלקים: render.yaml תואם למה שהשירות מחשב, השירות רץ על הגרסאות שהבדיקות רצו עליהן, והקורא
נשאר חבילה נקייה (התלות היחידה שלו בזמן ריצה היא pypdfium2, ולשירות אין python-bidi או cmark-gfm)."""

import ast
import re
import sys
import tempfile
import unittest
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from web import limits
from web.app import app

ROOT = Path(__file__).resolve().parent.parent
RENDER = (ROOT / "render.yaml").read_text(encoding="utf-8")
# הזיכרון (MB) והמעבד של התוכנית שב-render.yaml (https://render.com/docs/compute-plans)
PLANS = {"free": (512, 0.1), "0.5c-512mb": (512, 0.5), "starter": (512, 0.5), "1c-2g": (2048, 1.0),
         "standard": (2048, 1.0), "2c-4g": (4096, 2.0), "pro": (4096, 2.0)}


def render_value(key: str) -> str:
    found = re.search(rf"^\s*-\s*key:\s*{re.escape(key)}\s*\n\s*value:\s*(\S+)\s*$", RENDER, re.MULTILINE)
    if found is None:
        raise AssertionError(f"render.yaml: אין {key}")
    return found.group(1)


def render_field(name: str) -> str:
    found = re.search(rf"^\s*{re.escape(name)}:\s*(.+?)\s*$", RENDER, re.MULTILINE)
    if found is None:
        raise AssertionError(f"render.yaml: אין {name}")
    return found.group(1)


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    return names


class RenderTest(unittest.TestCase):
    def test_slots_in_render_match_the_formula(self):
        memory, cpus = PLANS[render_field("plan")]
        expected = min(limits.slots_for(memory * limits.MB), limits.cpu_slots(cpus))
        self.assertEqual(int(render_value("HEBREW_PDF_SLOTS")), expected)
        # ואותו חשבון כמו של השירות עצמו, כשהמגבלות כתובות ב-cgroup כמו בתוכנית
        root = Path(tempfile.mkdtemp())
        (root / "memory.max").write_text(str(memory * limits.MB))
        (root / "cpu.max").write_text(f"{int(cpus * 100000)} 100000")
        self.assertEqual(limits.capacity({}, root).slots, expected)

    def test_service_settings(self):
        self.assertEqual(render_field("region"), "frankfurt")
        self.assertEqual(render_field("startCommand"), "python -m web")
        self.assertEqual(render_value("HOST"), "0.0.0.0")
        self.assertGreaterEqual(int(render_field("maxShutdownDelaySeconds")), limits.TIMEOUT_SECONDS)
        health = render_field("healthCheckPath")
        self.assertIn(health, {route.path for route in app.routes})

    def test_python_version(self):
        pinned = (ROOT / ".python-version").read_text().strip()
        self.assertEqual(pinned, f"{sys.version_info.major}.{sys.version_info.minor}",
                         "הבדיקות רצות על גרסה אחרת מזו שב-Render")


# החבילות שהשירות מייבא ישירות (web/*.py). כל השאר ב-web/requirements.txt הוא מה שהן מושכות
DIRECT = ("pypdfium2", "fastapi", "starlette", "uvicorn")


def pins() -> dict[str, str]:
    """הגרסאות הנעולות ב-web/requirements.txt, לפי שם מנורמל (PEP 503)."""
    found = {}
    for line in (ROOT / "web" / "requirements.txt").read_text().splitlines():
        line = line.split("#")[0].strip()
        if line and not line.startswith("-r"):
            name, version = line.split("==")
            found[canonicalize_name(name)] = version
    return found


def closure(names) -> set[str]:
    """החבילות הישירות וכל מה שהן מושכות, לפי התלויות שמותקנות בפועל (importlib.metadata), בלי extras, ועם התנאים
    (python_version וכו') של הסביבה הזו."""
    found: set[str] = set()
    todo = [canonicalize_name(name) for name in names]
    while todo:
        name = todo.pop()
        if name in found:
            continue
        found.add(name)
        for raw in metadata.distribution(name).requires or []:
            requirement = Requirement(raw)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                todo.append(canonicalize_name(requirement.name))
    return found


class DependenciesTest(unittest.TestCase):
    def test_the_lock_is_complete_and_installed(self):
        locked = pins()
        self.assertEqual(set(locked), closure(DIRECT), "web/requirements.txt לא נועל בדיוק את מה שהשירות מושך")
        for name, version in locked.items():
            self.assertEqual(metadata.version(name), version, name)

    def test_the_reader_stays_clean(self):
        self.assertEqual([line for line in (ROOT / "requirements.txt").read_text().splitlines() if line.strip()],
                         ["pypdfium2>=5.13"])
        allowed = set(sys.stdlib_module_names) | {"pypdfium2", "pypdfium2_raw", "hebrew_pdf"}
        for path in sorted((ROOT / "hebrew_pdf").glob("*.py")):
            with self.subTest(path=path.name):
                self.assertLessEqual(imports(path), allowed)

    def test_the_service_does_not_use_dev_tools(self):
        allowed = set(sys.stdlib_module_names) | {"pypdfium2", "pypdfium2_raw", "hebrew_pdf", "web", "fastapi",
                                                  "starlette", "uvicorn"}
        for path in sorted((ROOT / "web").glob("*.py")):
            with self.subTest(path=path.name):
                self.assertLessEqual(imports(path), allowed)
        for dev in ("python-bidi", "cmarkgfm", "weasyprint", "playwright", "packaging"):
            self.assertNotIn(dev, pins())


if __name__ == "__main__":
    unittest.main()
