"""מדידה: זמן, זמן מעבד ושיא זיכרון של המרה, לכל קובץ בסט, באותו מסלול שהשירות מריץ. לינוקס בלבד (/proc).

כל קובץ מומר בתהליך חדש משרת התהליכים, דרך אותה החלפה (conversion.exchange: הקובץ ב-pipe, התשובה כ-JSON) ואותה
פונקציה (conversion.outcome), ובסוף התהליך נקראים ממנו עצמו (/proc/self/status, מסמך הליבה proc(5)):
- VmHWM: שיא הזיכרון הפיזי (RSS) של התהליך. זה המספר שמולו נגזר כמה המרות נכנסות במקביל: שיא, ולא מה שנשאר
  בסוף (bugbot-rules/host-metric-in-container.md).
- VmPeak: שיא הזיכרון הווירטואלי. מולו נקבעת התקרה של כל תהליך (RLIMIT_AS, conversion._limit_memory), כי זה מה
  שהתקרה הזו מודדת.
- VmRSS בהתחלה: מה שהתהליך כבר מחזיק לפני ההמרה (העותק של שרת התהליכים, שרובו משותף איתו).
- זמן מעבד (resource.getrusage, ru_utime ועוד ru_stime): מולו נגזר כמה המרות יכולות לחלוק את המעבד ועדיין להסתיים
  בזמן (web/limits.py, cpu_slots).

ונמדד גם הבסיס של השירות: התהליך הזה (שמייבא את מה שהשרת מייבא) ושרת התהליכים. קובץ שההמרה שלו נכשלה (חריגה, או
תהליך שמת) נרשם בטבלה עם הקוד שלו, והמדידה ממשיכה לקובץ הבא.

שימוש (מתיקיית הריפו): python -m web.measure [קבצים...]. בלי קבצים: כל testset/pdfs. הפלט: טבלה למסך, מספרים בלבד
ושמות הקבצים של הסט, בלי טקסט מהקבצים.
"""

import argparse
import asyncio
import json
import resource
import time
from pathlib import Path

from web import conversion, limits

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


def _measured_child(source, answer, max_pages: int) -> None:
    """כמו conversion.child_main, בלי תקרת זיכרון (כדי למדוד את השיא האמיתי), ועם המדידה במקום התוצאה."""
    data = conversion.read_input(source)
    start = _status()["VmRSS"]
    began = time.perf_counter()
    try:
        result = conversion.outcome(data, max_pages)
        error = result.get("error")
        size = len(conversion.encode_answer(result))
        pages = len(result["result"]["pages"]) if "result" in result else 0
    except Exception as failure:  # מדידה: חריגה בקובץ אחד נרשמת בטבלה, בלי ההודעה שלה, והמדידה ממשיכה
        error, size, pages = conversion.safe_traceback(failure), 0, 0
    seconds = time.perf_counter() - began
    usage = resource.getrusage(resource.RUSAGE_SELF)
    status = _status()
    conversion.write_answer(answer, conversion.encode_answer({
        "seconds": seconds, "cpu": usage.ru_utime + usage.ru_stime, "hwm": status["VmHWM"], "peak": status["VmPeak"],
        "start": start, "pages": pages, "error": error, "answer": size}))


async def _measure(path: Path) -> dict | str:
    try:
        raw = await conversion.exchange(_measured_child, path.read_bytes(), (10_000,), timeout=3600,
                                        max_answer=limits.MAX_ANSWER)
    except conversion.ConversionFailed as failed:
        return failed.code
    return json.loads(raw) if raw else conversion.CRASHED


def _forkserver_pid() -> int | None:
    from multiprocessing import forkserver
    return forkserver._forkserver._forkserver_pid


async def main(paths: list[Path]) -> None:
    conversion.start_worker_server()
    await asyncio.sleep(1)  # שרת התהליכים מייבא את החבילה ברקע; בלי ההמתנה הבסיס שלו היה נמדד לפני הייבוא
    print(f"השירות (התהליך הזה): VmRSS {_status()['VmRSS'] / MB:.1f}MB")
    server = _forkserver_pid()
    if server is not None:
        print(f"שרת התהליכים: VmRSS {_status(server)['VmRSS'] / MB:.1f}MB")
    print()
    print("| קובץ | גודל | עמודים | שניות | זמן מעבד | שיא RSS | שיא וירטואלי | RSS בהתחלה | התשובה (JSON) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for path in paths:
        m = await _measure(path)
        if isinstance(m, str):
            print(f"| {path.name} | {path.stat().st_size / MB:.2f}MB | {m} | | | | | | |")
            continue
        print(f"| {path.name} | {path.stat().st_size / MB:.2f}MB | {m['pages'] or m['error']} | {m['seconds']:.2f} "
              f"| {m['cpu']:.2f} | {m['hwm'] / MB:.1f}MB | {m['peak'] / MB:.1f}MB | {m['start'] / MB:.1f}MB "
              f"| {m['answer'] / 1024:.0f}KB |")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="python -m web.measure", description=__doc__.split("\n")[0])
    parser.add_argument("pdfs", nargs="*", type=Path)
    args = parser.parse_args()
    asyncio.run(main(args.pdfs or sorted((ROOT / "testset" / "pdfs").glob("*.pdf"))))
