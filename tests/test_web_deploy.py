"""הפריסה והגבולות בין החלקים: render.yaml תואם למה שהשירות מחשב, השירות רץ על הגרסאות שהבדיקות רצו עליהן, והקורא
נשאר חבילה נקייה (התלות היחידה שלו בזמן ריצה היא pypdfium2, ולשירות אין python-bidi או cmark-gfm)."""

import ast
import re
import sys
import unittest
from importlib import metadata
from pathlib import Path

from web import limits
from web.app import app

ROOT = Path(__file__).resolve().parent.parent
RENDER = (ROOT / "render.yaml").read_text(encoding="utf-8")
# הזיכרון של התוכנית שב-render.yaml (https://render.com/docs/compute-plans)
PLAN_MEMORY = {"0.5c-512mb": 512, "starter": 512, "free": 512, "1c-2g": 2048, "standard": 2048}


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
        memory = PLAN_MEMORY[render_field("plan")] * limits.MB
        self.assertEqual(int(render_value("HEBREW_PDF_SLOTS")), limits.slots_for(memory))

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


class DependenciesTest(unittest.TestCase):
    def test_the_service_runs_the_tested_versions(self):
        pins = dict(re.findall(r"^([A-Za-z0-9_.-]+)==(\S+)", (ROOT / "web" / "requirements.txt").read_text(), re.MULTILINE))
        self.assertEqual(set(pins), {"fastapi", "starlette", "uvicorn"})
        for name, version in pins.items():
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
        # השורות שהן דרישה, בלי ההערות (ההערה בקובץ מזכירה את python-bidi בכוונה)
        service = [line.split("#")[0].strip().lower() for line in (ROOT / "web" / "requirements.txt").read_text().splitlines()]
        self.assertEqual([line for line in service if line], ["-r ../requirements.txt", "fastapi==0.162.0",
                                                              "starlette==1.7.0", "uvicorn==0.54.0"])


if __name__ == "__main__":
    unittest.main()
