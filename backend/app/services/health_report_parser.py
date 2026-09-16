"""体检报告解析服务

采用规则引擎从体检报告文本中抽取关键指标,并给出分级评估。
解析结果结构:
{
  "blood_glucose": 6.3, "blood_pressure_systolic": 145, ...,
  "indicators": [{"key","name","value","unit","level","reference","advice"}],
  "risk_tags": ["血糖偏高", "血压偏高"],
  "summary": "文本摘要",
  "abnormal_count": 2
}
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# 指标定义:(key, 中文名, 单位, 参考范围, 解析正则列表)
_METRIC_PATTERNS: List[Dict[str, Any]] = [
    {
        "key": "blood_glucose",
        "name": "空腹血糖",
        "unit": "mmol/L",
        "reference": "3.9 ~ 6.1",
        "patterns": [r"(?:空腹)?血糖[^\d\-]{0,12}(\d+(?:\.\d+)?)"],
        "cast": float,
    },
    {
        "key": "blood_pressure_systolic",
        "name": "收缩压",
        "unit": "mmHg",
        "reference": "90 ~ 139",
        "patterns": [r"收缩压[^\d]{0,12}(\d{2,3})", r"高压[^\d]{0,12}(\d{2,3})"],
        "cast": lambda v: int(float(v)),
    },
    {
        "key": "blood_pressure_diastolic",
        "name": "舒张压",
        "unit": "mmHg",
        "reference": "60 ~ 89",
        "patterns": [r"舒张压[^\d]{0,12}(\d{2,3})", r"低压[^\d]{0,12}(\d{2,3})"],
        "cast": lambda v: int(float(v)),
    },
    {
        "key": "uric_acid",
        "name": "尿酸",
        "unit": "μmol/L",
        "reference": "155 ~ 420",
        "patterns": [r"尿酸[^\d]{0,12}(\d+(?:\.\d+)?)"],
        "cast": float,
    },
    {
        "key": "cholesterol",
        "name": "总胆固醇",
        "unit": "mmol/L",
        "reference": "< 5.2",
        "patterns": [r"(?:总)?胆固醇[^\d]{0,12}(\d+(?:\.\d+)?)"],
        "cast": float,
    },
    {
        "key": "triglycerides",
        "name": "甘油三酯",
        "unit": "mmol/L",
        "reference": "< 1.7",
        "patterns": [r"甘油三酯[^\d]{0,12}(\d+(?:\.\d+)?)"],
        "cast": float,
    },
]

_BP_COMBO = re.compile(r"血压[^\d]{0,12}(\d{2,3})\s*/\s*(\d{2,3})")


def _level_by_ranges(value: float, thresholds: List[tuple]) -> str:
    """thresholds: [(上限, 等级), ...] 按顺序匹配"""
    for upper, level in thresholds:
        if value < upper:
            return level
    return thresholds[-1][1]


class HealthReportParser:
    """体检报告解析器(规则引擎)"""

    def parse(self, content: str) -> Dict[str, Any]:
        content = content or ""
        values: Dict[str, Optional[float]] = {}

        # 组合血压 "血压 145/95" 优先
        bp_match = _BP_COMBO.search(content)
        if bp_match:
            values["blood_pressure_systolic"] = int(bp_match.group(1))
            values["blood_pressure_diastolic"] = int(bp_match.group(2))

        for metric in _METRIC_PATTERNS:
            key = metric["key"]
            if values.get(key) is not None:
                continue
            for pattern in metric["patterns"]:
                m = re.search(pattern, content)
                if m:
                    try:
                        values[key] = metric["cast"](m.group(1))
                    except (TypeError, ValueError):
                        pass
                    break
            values.setdefault(key, None)

        indicators = self._evaluate(values, content)
        risk_tags = [i["name"] + i["level"] for i in indicators if i["level"] not in ("正常",)]
        abnormal_count = sum(1 for i in indicators if i["level"] not in ("正常",))

        result: Dict[str, Any] = {k: values.get(k) for k in (
            "blood_glucose",
            "blood_pressure_systolic",
            "blood_pressure_diastolic",
            "uric_acid",
            "cholesterol",
            "triglycerides",
        )}
        result["indicators"] = indicators
        result["risk_tags"] = risk_tags
        result["abnormal_count"] = abnormal_count
        result["summary"] = self._summary(indicators, abnormal_count)
        result["engine"] = "rule-based"
        return result

    # ------------------------------------------------------------------ 评估
    def _evaluate(self, values: Dict[str, Optional[float]], content: str) -> List[Dict[str, Any]]:
        indicators: List[Dict[str, Any]] = []

        glucose = values.get("blood_glucose")
        if glucose is not None:
            level = _level_by_ranges(
                glucose,
                [
                    (3.9, "偏低"),
                    (6.1, "正常"),
                    (7.0, "偏高(空腹血糖受损)"),
                    (float("inf"), "显著偏高(疑似糖尿病)"),
                ],
            )
            indicators.append(
                self._item("blood_glucose", "空腹血糖", glucose, "mmol/L", level, "3.9 ~ 6.1",
                           "控制精制碳水,主食粗细搭配,进餐顺序:蔬菜→蛋白质→主食")
            )

        sys_v, dia_v = values.get("blood_pressure_systolic"), values.get("blood_pressure_diastolic")
        if sys_v is not None and dia_v is not None:
            if sys_v >= 160 or dia_v >= 100:
                level, advice = "2级高血压", "严格限盐(<5g/日),尽快就医评估用药"
            elif sys_v >= 140 or dia_v >= 90:
                level, advice = "1级高血压", "限盐补钾,推荐 DASH 饮食,规律有氧运动"
            elif sys_v >= 120 or dia_v >= 80:
                level, advice = "正常高值", "减少隐性钠摄入,控制体重,监测血压"
            elif sys_v < 90 or dia_v < 60:
                level, advice = "偏低", "保证充足饮水与蛋白质,避免久站和突然起身"
            else:
                level, advice = "正常", "保持清淡饮食与规律作息"
            indicators.append(
                self._item(
                    "blood_pressure",
                    "血压",
                    f"{int(sys_v)}/{int(dia_v)}",
                    "mmHg",
                    level,
                    "90 ~ 139 / 60 ~ 89",
                    advice,
                )
            )

        uric = values.get("uric_acid")
        if uric is not None:
            if uric >= 540:
                level, advice = "显著偏高", "限制高嘌呤食物,每日饮水2000~3000ml,及时就诊"
            elif uric >= 420:
                level, advice = "偏高", "少食内脏海鲜,禁啤酒,多吃蔬菜和低脂奶"
            else:
                level, advice = "正常", "保持饮水量,避免高嘌呤饮食"
            indicators.append(
                self._item("uric_acid", "尿酸", uric, "μmol/L", level, "155 ~ 420", advice)
            )

        tc = values.get("cholesterol")
        if tc is not None:
            level = _level_by_ranges(
                tc, [(5.2, "正常"), (6.2, "边缘升高"), (float("inf"), "升高")]
            )
            indicators.append(
                self._item("cholesterol", "总胆固醇", tc, "mmol/L", level, "< 5.2",
                           "限制饱和脂肪与内脏,增加可溶性膳食纤维和深海鱼")
            )

        tg = values.get("triglycerides")
        if tg is not None:
            level = _level_by_ranges(
                tg, [(1.7, "正常"), (2.3, "边缘升高"), (float("inf"), "升高")]
            )
            indicators.append(
                self._item("triglycerides", "甘油三酯", tg, "mmol/L", level, "< 1.7",
                           "减少精制糖与酒精,控制总热量,增加omega-3摄入")
            )

        if not indicators and content.strip():
            indicators.append(
                self._item(
                    "raw", "报告内容", "-", "-", "未识别",
                    "-",
                    "未能从文本中识别标准指标,请在医生指导下结合原报告解读",
                )
            )
        return indicators

    @staticmethod
    def _item(key: str, name: str, value: Any, unit: str, level: str, reference: str,
              advice: str) -> Dict[str, Any]:
        return {
            "key": key,
            "name": name,
            "value": value,
            "unit": unit,
            "level": level,
            "reference": reference,
            "advice": advice,
        }

    @staticmethod
    def _summary(indicators: List[Dict[str, Any]], abnormal_count: int) -> str:
        if not indicators:
            return "未提供可解析的体检数据。"
        if abnormal_count == 0:
            return f"共解析 {len(indicators)} 项指标,均在参考范围内,整体健康状况良好。"
        abnormal = "、".join(
            f"{i['name']}({i['value']}{i['unit']},{i['level']})"
            for i in indicators
            if i["level"] != "正常"
        )
        return f"共解析 {len(indicators)} 项指标,其中 {abnormal_count} 项需要关注:{abnormal}。"
