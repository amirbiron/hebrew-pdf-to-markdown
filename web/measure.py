"""מדידה: זמן ושיא זיכרון של המרה, לכל קובץ בסט, באותו מסלול שהשירות מריץ.

כל קובץ מומר בתהליך חדש משרת התהליכים (web/conversion.py), עם אותה פונקציה (conversion.outcome) ואותו ייבוא מראש,
ובסוף התהליך נקראים ממנו עצמו (/proc/self/status, מסמך הליבה proc(5)):
- VmHWM: שיא הזיכרון הפיזי (RSS) של התהליך. זה המספר שמולו נגזר כמה המרות נכנסות במקביל: שיא, ולא מה שנשאר
  בסוף (bugbot-rules/host-metric-in-container.md).
- VmPeak: שיא הזיכרון הווירטואלי. מולו נקבעת התקרה של כל תהליך (RLIMIT_AS, conversion._limit_memory), כי זה מה
  שהתקרה הזו מודדת.
- VmRSS בהתחלה: מה שהתהליך כבר מחזיק לפני ההמרה (העותק של שרת התהליכים, שרובו משותף איתו).

ונמדד גם הבסיס של השירות: התהליך הזה (שמייבא את מה שהשרת מייבא) ושרת התהליכים.

שימוש (מתיקיית הריפו): python -m web.measure [קבצים...]. בלי קבצים: כל testset/pdfs. הפלט: טבלה למסך, מספרים בלבד
ושמות הקבצים של הסט, בלי טקסט מהקבצים.
"""

import argparse
import asyncio
import os
import pickle
import time
from pathlib import Path

from web import conversion

ROOT = Path(__file__).resolve().parent.parent
MB = 1024 * 1024


def _status(pid: int | str = "self") -> dict[str, int]:
    """השדות Vm* של /proc/<pid>/status, בבתים."""
    fields = {}
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        name, _, value = line.partition(":")
        if name.startswith("Vm") and value.strip().endswith("kB"):
            fields[name] = int(value.split()[0]) * 1024
    return fields


def _measured_child(data: bytes, max_pages: int, sender) -> None:
    start = _status()["VmRSS"]
    began = time.perf_counter()
    result = conversion.outcome(data, max_pages)
    seconds = time.perf_counter() - began
    status = _status()
    pages = len(result["result"]["pages"]) if "result" in result else 0
    sender.send({"seconds": seconds, "hwm": status["VmHWM"], "peak": status["VmPeak"], "start": start,
                 "pages": pages, "error": result.get("error"), "payload": len(pickle.dumps(result))})
    sender.close()


async def _measure(path: Path, max_pages: int) -> dict:
    receiver, sender = conversion._CONTEXT.Pipe(duplex=False)
    process = conversion._CONTEXT.Process(target=_measured_child, args=(path.read_bytes(), max_pages, sender))
    process.start()
    sender.close()
    try:
        await conversion._readable(receiver.fileno())
        return receiver.recv()
    finally:
        receiver.close()
        await conversion._stop(process)


def _forkserver_pid() -> int | None:
    from multiprocessing import forkserver
    return forkserver._forkserver._forkserver_pid


async def main(paths: list[Path]) -> None:
    conversion.start_worker_server()
    print(f"השירות (התהליך הזה): VmRSS {_status()['VmRSS'] / MB:.1f}MB")
    server = _forkserver_pid()
    if server is not None:
        print(f"שרת התהליכים: VmRSS {_status(server)['VmRSS'] / MB:.1f}MB")
    print()
    print("| קובץ | גודל | עמודים | שניות | שיא RSS | שיא וירטואלי | RSS בהתחלה | התשובה (pickle) |")
    print("|---|---|---|---|---|---|---|---|")
    for path in paths:
        m = await _measure(path, max_pages=10_000)
        print(f"| {path.name} | {path.stat().st_size / MB:.2f}MB | {m['pages'] or m['error']} | {m['seconds']:.2f} "
              f"| {m['hwm'] / MB:.1f}MB | {m['peak'] / MB:.1f}MB | {m['start'] / MB:.1f}MB | {m['payload'] / 1024:.0f}KB |")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="python -m web.measure", description=__doc__.split("\n")[0])
    parser.add_argument("pdfs", nargs="*", type=Path)
    args = parser.parse_args()
    asyncio.run(main(args.pdfs or sorted((ROOT / "testset" / "pdfs").glob("*.pdf"))))
    os._exit(0)
