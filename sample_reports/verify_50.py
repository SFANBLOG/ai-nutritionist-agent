"""校验 reports_50/ 下的 50 份体检报告能被后端解析器正确解析。

用法(在 sample_reports/ 目录下执行):
    python verify_50.py

会断言每份报告的 6 项核心指标(血糖/收缩压/舒张压/尿酸/总胆固醇/甘油三酯)抽取值 == 设计值、
指标数 == 5,并打印每份的 abnormal_count 与等级;同时确认正常(0 异常)与异常(>0 异常)均存在。
改动报告后请重新运行本脚本,避免出现「报告能上传但解析不出指标」的情况。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(HERE))

from generate_50 import PERSONAS, build, render  # noqa: E402
from app.services.health_report_parser import HealthReportParser  # noqa: E402


def main() -> int:
    parser = HealthReportParser()
    passed = failed = 0
    abnormal_reports = 0
    normal_reports = 0

    for i, raw in enumerate(PERSONAS, 1):
        p = build(raw, i)
        path = HERE / "reports_50" / p["file"]
        if not path.exists():
            print(f"[MISS] {p['file']} 不存在,请先运行 generate_50.py")
            failed += 1
            continue

        text = path.read_text(encoding="utf-8")
        r = parser.parse(text)
        lab = p["lab"]

        expect = {
            "blood_glucose": float(lab["空腹血糖(FPG)"]),
            "blood_pressure_systolic": float(p["sys"]),
            "blood_pressure_diastolic": float(p["dia"]),
            "uric_acid": float(lab["尿酸(UA)"]),
            "cholesterol": float(lab["总胆固醇(TC)"]),
            "triglycerides": float(lab["甘油三酯(TG)"]),
        }

        errs = []
        for k, ev in expect.items():
            av = r.get(k)
            if av is None:
                errs.append(f"{k} 未解析(期望 {ev})")
            elif abs(float(av) - ev) > 1e-6:
                errs.append(f"{k}={av}(期望 {ev})")
        if len(r["indicators"]) != 5:
            errs.append(f"指标数={len(r['indicators'])}(期望 5)")

        if errs:
            failed += 1
            print(f"[FAIL] {p['file']}")
            for e in errs:
                print(f"       !! {e}")
        else:
            passed += 1
            levels = "、".join(f"{it['name']}({it['level']})" for it in r["indicators"])
            if r["abnormal_count"] == 0:
                normal_reports += 1
            else:
                abnormal_reports += 1
            print(f"[PASS] {p['file']}  异常{r['abnormal_count']}  {levels}")

    print(f"\n解析校验:{passed} 通过 / {failed} 失败(共 {len(PERSONAS)} 份)")
    print(f"正常报告(0 异常):{normal_reports} 份;异常报告(>0 异常):{abnormal_reports} 份")

    ok = (failed == 0) and (normal_reports > 0) and (abnormal_reports > 0)
    if not ok:
        print("\n[WARN] 未满足「正常与异常均存在且全部解析通过」的预期。")
    return 1 if (failed or not ok) else 0


if __name__ == "__main__":
    raise SystemExit(main())
