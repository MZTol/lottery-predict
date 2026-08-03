import argparse
import os
import runpy
import sys

from crawler import output_file
from utils import ensure_fresh
import review_report
import site_index


DIR = os.path.dirname(__file__)
LOTTERIES = ("kl8", "dlt", "ssq")
SCRIPT_BY_LOTTERY = {
    "kl8": ("1.py", ["10"]),
    "dlt": ("2.py", []),
    "ssq": ("3.py", []),
}


def _targets(value):
    if value == "all":
        return list(LOTTERIES)
    if value not in LOTTERIES:
        raise SystemExit(f"未知彩种: {value}")
    return [value]


def _run_script(script_name, args=None):
    args = args or []
    script_path = os.path.join(DIR, script_name)
    old_argv = sys.argv[:]
    try:
        sys.argv = [script_path] + list(args)
        runpy.run_path(script_path, run_name="__main__")
    finally:
        sys.argv = old_argv


def fetch(target):
    for lotid in _targets(target):
        ensure_fresh(output_file(lotid), lotid, max_age_hours=1)


def predict(target):
    for lotid in _targets(target):
        script, args = SCRIPT_BY_LOTTERY[lotid]
        _run_script(script, args)


def review(target):
    review_report.main(["review_report.py", target])


def site(report_dir=None):
    report_dir = report_dir or os.path.join(DIR, "reports")
    path = site_index.generate_site(report_dir, updated_at=os.environ.get("SITE_UPDATED_AT"))
    print(f"首页已生成: {path}")


def run(target):
    predict(target)
    review(target)
    site()


def main(argv=None):
    parser = argparse.ArgumentParser(description="彩票预测统一入口")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("fetch", "predict", "review", "run"):
        p = sub.add_parser(name)
        p.add_argument("target", nargs="?", default="all")

    p_site = sub.add_parser("site")
    p_site.add_argument("report_dir", nargs="?")

    args = parser.parse_args(argv)
    if args.command == "fetch":
        fetch(args.target)
    elif args.command == "predict":
        predict(args.target)
    elif args.command == "review":
        review(args.target)
    elif args.command == "site":
        site(args.report_dir)
    elif args.command == "run":
        run(args.target)


if __name__ == "__main__":
    main()
