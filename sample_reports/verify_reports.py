"""校验 sample_reports/ 下的体检报告能被后端解析器正确解析。

用法(在 sample_reports/ 目录下执行):
    python verify_reports.py

会断言每份报告的 6 项指标抽取值 == 设计值、指标数 == 5、异常项数 == 设计值。
改动报告后请重新运行本脚本,避免出现「报告能上传但解析不出指标」的情况。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(HERE))

from _generate_reports import PERSONAS  # noqa: E402

from app.services.health_report_parser import HealthReportParser  # noqa: E402

# 各报告设计上的异常项数量(仅统计解析器覆盖的 5 个指标:血压/血糖/尿酸/总胆固醇/甘油三酯)
EXPECTED_ABNORMAL = {
    "张建国": 5, "李秀兰": 4, "王海涛": 3, "陈静": 0, "赵国强": 5,
    "刘敏": 3, "孙浩": 2, "周雅琴": 1, "吴伟": 3, "郑丽华": 2,
}


def main() -> int:
    parser = HealthReportParser()
    passed = failed = 0

    for p in PERSONAS:
        path = HERE / p["file"]
        if not path.exists():
            print(f"[MISS] {p['file']} 不存在,请先运行 _generate_reports.py")
            failed += 1
            continue

        r = parser.parse(path.read_text(encoding="utf-8"))
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
        if r["abnormal_count"] != EXPECTED_ABNORMAL[p["name"]]:
            errs.append(f"异常项={r['abnormal_count']}(期望 {EXPECTED_ABNORMAL[p['name']]})")
        if len(r["indicators"]) != 5:
            errs.append(f"指标数={len(r['indicators'])}(期望 5)")

        if errs:
            failed += 1
            print(f"[FAIL] {p['file']}")
            for e in errs:
                print(f"       !! {e}")
        else:
            passed += 1
            print(f"[PASS] {p['file']}  "
                  f"血糖{r['blood_glucose']} " 
                  f"血压{r['blood_pressure_systolic']}/{r['blood_pressure_diastolic']} "
                  f"尿酸{r['uric_acid']} TC{r['cholesterol']} TG{r['triglycerides']} "
                  f"异常{r['abnormal_count']}")

    print(f"\n解析校验:{passed} 通过 / {failed} 失败(共 {len(PERSONAS)} 份)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
