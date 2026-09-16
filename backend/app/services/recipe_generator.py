"""食谱生成服务

职责:把 LLM 的自由文本输出规整为结构化的食谱数据(JSON),
并在缺少 LLM 能力时提供基于规则的模板食谱兜底,保证系统始终可用。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

MEAL_LABELS = {
    "breakfast": "早餐",
    "lunch": "午餐",
    "dinner": "晚餐",
    "snack": "加餐",
}

# 不同健康状况的膳食提示(用于模板兜底与审核校验)
CONDITION_RULES: List[Dict[str, Any]] = [
    {
        "tag": "血糖",
        "keywords": ["血糖", "糖尿病", "血糖受损"],
        "avoid": ["含糖饮料", "白粥", "糯米", "蜂蜜", "蔗糖", "果汁"],
        "prefer": ["燕麦", "荞麦", "藜麦", "糙米", "杂豆", "绿叶蔬菜"],
    },
    {
        "tag": "血压",
        "keywords": ["血压", "高血压"],
        "avoid": ["腌制品", "咸菜", "腊肉", "火腿", "方便面", "咸鱼"],
        "prefer": ["芹菜", "菠菜", "香蕉", "低脂奶", "紫菜"],
    },
    {
        "tag": "尿酸",
        "keywords": ["尿酸", "痛风"],
        "avoid": ["动物内脏", "沙丁鱼", "浓肉汤", "啤酒", "贝类", "虾蟹"],
        "prefer": ["低脂奶", "鸡蛋", "新鲜蔬菜", "樱桃"],
    },
    {
        "tag": "血脂",
        "keywords": ["胆固醇", "甘油三酯", "血脂"],
        "avoid": ["肥肉", "油炸", "奶油", "动物内脏", "黄油"],
        "prefer": ["深海鱼", "燕麦", "坚果", "橄榄油", "可溶性膳食纤维"],
    },
]


class RecipeGenerator:
    """食谱生成 / 规整器"""

    # ------------------------------------------------------------- 热量目标
    @staticmethod
    def estimate_target_calories(user_profile: Dict[str, Any]) -> int:
        """基于 Mifflin-St Jeor 估算每日目标热量"""
        age = user_profile.get("age") or 30
        height = user_profile.get("height") or 170
        weight = user_profile.get("weight") or 65
        gender = (user_profile.get("gender") or "female")
        if hasattr(gender, "value"):
            gender = gender.value
        if int(age) > 150 or float(height) > 250:
            return 1800

        bmr = 10 * float(weight) + 6.25 * float(height) - 5 * float(age)
        bmr += 5 if str(gender) == "male" else -161
        target = bmr * 1.375  # 轻度活动
        return int(round(max(1200, min(2800, target)) / 50.0) * 50)

    # ------------------------------------------------------------- LLM 解析
    @staticmethod
    def extract_json(text: str) -> Optional[Dict[str, Any]]:
        """从 LLM 输出中稳健提取 JSON 对象"""
        if not text:
            return None
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
        try:
            data = json.loads(cleaned)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
        return None

    def normalize(self, data: Dict[str, Any], fallback_name: str = "AI 个性化食谱") -> Dict[str, Any]:
        """把 LLM 返回的数据规整为标准结构"""
        meals_in = data.get("meals") or []
        meals: List[Dict[str, Any]] = []
        for m in meals_in:
            if not isinstance(m, dict):
                continue
            meal_type = str(m.get("meal_type") or m.get("type") or "lunch").lower()
            if meal_type not in MEAL_LABELS:
                meal_type = "lunch"
            dishes = []
            for d in m.get("dishes") or []:
                if not isinstance(d, dict):
                    continue
                dishes.append(
                    {
                        "name": str(d.get("name") or "菜品"),
                        "description": str(d.get("description") or ""),
                        "ingredients": self._as_text(d.get("ingredients")),
                        "cooking_method": self._as_text(d.get("cooking_method")),
                        "calories": self._as_int(d.get("calories")),
                        "protein": self._as_float(d.get("protein")),
                        "carbohydrate": self._as_float(d.get("carbohydrate")),
                        "fat": self._as_float(d.get("fat")),
                        "fiber": self._as_float(d.get("fiber")),
                        "tips": str(d.get("tips") or ""),
                    }
                )
            meal_cal = sum(d["calories"] for d in dishes)
            meals.append(
                {
                    "meal_type": meal_type,
                    "meal_label": MEAL_LABELS[meal_type],
                    "target_calories": self._as_int(m.get("target_calories")) or meal_cal,
                    "actual_calories": meal_cal,
                    "dishes": dishes,
                }
            )

        nutrition = data.get("nutrition_info") or {}
        total_calories = self._as_int(nutrition.get("calories")) or sum(
            m["actual_calories"] for m in meals
        )
        nutrition_info = {
            "calories": total_calories,
            "protein": self._as_float(nutrition.get("protein")) or self._sum(meals, "protein"),
            "carbs": self._as_float(nutrition.get("carbs")) or self._sum(meals, "carbohydrate"),
            "fat": self._as_float(nutrition.get("fat")) or self._sum(meals, "fat"),
            "fiber": self._as_float(nutrition.get("fiber")) or self._sum(meals, "fiber"),
        }

        return {
            "name": str(data.get("name") or fallback_name),
            "description": str(data.get("description") or ""),
            "nutrition_info": nutrition_info,
            "total_calories": total_calories,
            "meals": meals,
            "tips": [str(t) for t in (data.get("tips") or []) if t],
        }

    # ------------------------------------------------------------- 模板兜底
    # 按天轮换的菜品池:保证相邻天数主菜不重复,且均不含任何健康状况的禁忌食材
    # 7 天轮换菜品池:保证一周内每日主菜不重复,相邻天也尽量错开;
    # 全部为低GI/低盐/低脂的慢病友好基础组合,命中健康状况禁忌时由 _sanitize_meals 净化。
    # 仅晚餐索引 1 为海鲜(白灼虾仁),高尿酸场景会自动跳过该变体。
    _BREAKFAST_POOL = [
        [("燕麦牛奶粥", "燕麦片40g+低脂牛奶250ml+蓝莓50g", "水煮", 300, 13, 45, 8, 6,
          "燕麦为低GI主食,有助于平稳餐后血糖"), ("水煮蛋", "鸡蛋1个", "水煮8分钟", 72, 6.5, 0.6, 4.7, 0, "优质蛋白来源")],
        [("全麦面包+煎蛋", "全麦面包2片+鸡蛋1个+无糖豆浆250ml", "少油煎", 320, 15, 38, 10, 5,
          "全谷物提供缓释碳水,饱腹更久"), ("圣女果", "圣女果100g", "生食", 30, 1, 6, 0, 1, "补充番茄红素")],
        [("玉米+鸡蛋+牛奶", "甜玉米1根+鸡蛋1个+低脂牛奶250ml", "水煮", 330, 16, 40, 9, 6,
          "粗细搭配,膳食纤维丰富")],
        [("藜麦粥+蒸蛋", "藜麦30g+大米20g煮粥+鸡蛋1个", "煮+蒸", 310, 14, 42, 8, 5,
          "藜麦含完整蛋白,升糖平缓"), ("凉拌菠菜", "菠菜150g+白芝麻", "焯拌", 60, 5, 5, 3, 5, "补叶酸与铁")],
        [("杂粮煎饼+牛奶", "全麦粉煎饼1张(少油)+低脂牛奶250ml", "少油煎", 330, 14, 40, 10, 4,
          "全谷物早餐,搭配奶类补钙"), ("苹果", "苹果1个", "生食", 95, 0.2, 25, 0.2, 4, "富含果胶")],
        [("红薯小米粥+蛋", "红薯80g+小米30g煮粥+鸡蛋1个", "煮", 300, 13, 44, 7, 5,
          "薯类替代部分主食,高纤维"), ("黄瓜条", "黄瓜100g", "生食", 16, 0.8, 3, 0.2, 1, "清爽低热量")],
        [("希腊酸奶+燕麦+莓", "无糖希腊酸奶150g+燕麦片30g+草莓50g", "直接食用", 300, 16, 32, 9, 4,
          "高蛋白酸奶+抗氧化物,饱腹持久")],
    ]
    _LUNCH_POOL = [
        [("杂粮饭", "糙米+藜麦+黑米 共100g(生重)", "电饭煲蒸煮", 350, 8, 72, 2.5, 4, "粗细搭配降低餐后血糖峰值"),
         ("清蒸鲈鱼", "鲈鱼150g+姜丝+葱段", "清蒸10分钟", 180, 28, 0, 6, 0, "深海鱼类富含omega-3,抗炎降脂"),
         ("蒜蓉西兰花", "西兰花200g+蒜末", "快炒少油", 90, 6, 10, 3, 6, "深色蔬菜补充钾与膳食纤维")],
        [("鸡丝荞麦面", "荞麦面80g+鸡胸肉丝100g+黄瓜丝", "煮+拌", 360, 30, 45, 8, 5, "荞麦低GI,鸡胸高蛋白低脂"),
         ("凉拌菠菜", "菠菜200g+白芝麻", "焯拌", 70, 5, 6, 3, 5, "补充叶酸与铁")],
        [("番茄豆腐煲", "北豆腐150g+番茄+鸡蛋1个", "炖煮", 240, 18, 12, 12, 4, "植物蛋白+番茄红素,清淡高纤"),
         ("糙米饭", "糙米100g(生重)", "蒸煮", 350, 8, 72, 2.5, 4, "缓释碳水")],
        [("燕麦饭+蒸鸡胸", "燕麦米+大米共100g+鸡胸肉120g(蒸)", "蒸煮", 360, 32, 44, 7, 5, "高蛋白+β葡聚糖,控血脂"),
         ("蒜蓉油麦菜", "油麦菜200g+蒜末", "快炒少油", 70, 3, 6, 3, 5, "绿叶菜补钾")],
        [("荞麦饭+炖瘦牛肉", "荞麦米+大米共100g+番茄炖瘦牛肉80g", "煮+炖", 380, 28, 48, 9, 5, "瘦牛肉补铁,荞麦低GI"),
         ("清炒小白菜", "小白菜200g", "快炒少油", 60, 3, 5, 3, 4, "维C与膳食纤维")],
        [("黑米饭+白切鸡", "黑米+大米共100g+去皮鸡腿肉100g(水煮切片)", "煮", 370, 28, 46, 8, 5, "黑米花青素,鸡腿去皮减脂"),
         ("凉拌秋葵", "秋葵150g", "焯拌", 50, 2, 6, 1, 4, "黏液蛋白益肠胃")],
        [("杂粮饭+家常豆腐", "糙米+藜麦共100g+北豆腐150g红烧", "蒸煮+烧", 360, 20, 45, 10, 5, "植物蛋白+全谷物"),
         ("白灼生菜", "生菜200g+生抽", "白灼", 50, 2, 5, 0, 4, "低热量高纤维")],
    ]
    _DINNER_POOL = [
        [("香煎鸡胸肉", "鸡胸肉120g+黑胡椒", "少油煎制", 200, 30, 1, 7, 0, "高蛋白低脂肪"),
         ("藜麦蔬菜沙拉", "藜麦60g+生菜+番茄+黄瓜+紫甘蓝", "凉拌橄榄油", 260, 9, 40, 9, 8, "低热量高纤维,晚餐控总热量")],
        [("白灼虾仁", "虾仁120g+姜片", "白灼", 130, 24, 2, 2, 0, "优质蛋白低脂(海鲜,高尿酸者自动替换)"),
         ("清炒时蔬", "西兰花+胡萝卜200g", "快炒少油", 90, 5, 10, 3, 6, "丰富维生素"),
         ("红薯饭", "红薯+大米100g", "蒸煮", 300, 6, 60, 1, 5, "薯类替代部分主食")],
        [("蒸蛋羹+豆腐", "鸡蛋1个+嫩豆腐100g", "蒸", 180, 16, 4, 10, 2, "易消化的动植物双蛋白"),
         ("杂粮粥", "小米+燕麦30g", "煮", 200, 6, 35, 3, 4, "暖胃低负担")],
        [("鸡胸蔬菜卷", "生菜叶包鸡胸肉丝100g+黄瓜+彩椒", "凉拌", 220, 28, 6, 8, 5, "高蛋白低碳水,清爽晚餐"),
         ("小米粥", "小米30g", "煮", 110, 3, 22, 1, 2, "易消化")],
        [("番茄鸡蛋汤面", "全麦面60g+番茄+鸡蛋1个", "煮汤", 280, 14, 42, 7, 4, "全麦面缓释碳水"),
         ("凉拌菠菜", "菠菜200g", "焯拌", 60, 5, 5, 3, 5, "补铁")],
        [("豆腐蔬菜煲", "北豆腐150g+白菜+香菇", "炖煮", 220, 16, 10, 11, 5, "植物蛋白+菌菇多糖"),
         ("糙米饭", "糙米80g(生重)", "蒸煮", 280, 6, 58, 2, 3, "缓释碳水")],
        [("瘦牛肉炒西兰花", "瘦牛肉80g+西兰花200g", "快炒少油", 240, 26, 8, 11, 6, "补铁+高纤"),
         ("红薯饭", "红薯+大米100g", "蒸煮", 300, 6, 60, 1, 5, "薯类替代主食")],
    ]
    _SNACK_POOL = [
        [("原味坚果", "核桃2颗+巴旦木5粒", "直接食用", 130, 4, 5, 11, 2, "适量坚果有益心血管,控制在10g")],
        [("低脂酸奶+蓝莓", "无糖低脂酸奶150g+蓝莓50g", "直接食用", 140, 6, 14, 4, 2, "益生菌+抗氧化物")],
        [("苹果+核桃", "苹果1个+核桃1颗", "直接食用", 150, 2, 25, 5, 4, "水果+坚果,加餐轻盈")],
        [("圣女果+黄瓜条", "圣女果100g+黄瓜100g", "生食", 45, 2, 9, 0, 3, "低热量高水分,解馋无负担")],
        [("无糖豆浆+南瓜子", "无糖豆浆200ml+南瓜子10g", "直接食用", 130, 7, 8, 8, 2, "植物蛋白+镁")],
        [("柚子瓣+腰果", "柚子150g+腰果3粒", "直接食用", 140, 3, 22, 5, 3, "维C+健康脂肪")],
        [("煮毛豆", "带壳毛豆80g(去壳约50g)", "水煮", 110, 10, 9, 4, 4, "豆制品补蛋白与膳食纤维")],
    ]
    # 禁忌命中时的安全替身菜品(绝不出现在任何 avoid 列表)
    _SAFE_DISH = ("清炒时蔬", "西兰花+胡萝卜+木耳200g", "快炒少油", 90, 5, 10, 3, 6, "低热量安全蔬菜,适合多数慢病")

    def build_template_recipe(
        self,
        parsed_metrics: Dict[str, Any],
        user_profile: Dict[str, Any],
        preferences: List[Dict[str, Any]],
        knowledge_snippets: Optional[List[str]] = None,
        day_index: int = 0,
    ) -> Dict[str, Any]:
        """在无 LLM 可用时,基于规则生成一份营养均衡的模板食谱

        day_index 用于相邻天数轮换主菜,避免连续重复;同时按健康状况禁忌做
        净化(尿酸相关禁忌海鲜、其它 avoid 食材),保证安全性。
        """
        target = self.estimate_target_calories(user_profile)
        conditions = self._match_conditions(parsed_metrics)
        tags = {c["tag"] for c in conditions}
        disliked = {p["preference_value"] for p in preferences if p["preference_type"] == "disliked_food"}
        allergies = {p["preference_value"] for p in preferences if p["preference_type"] == "allergy"}

        variant = day_index % 7  # 7 天轮换,周/月方案每日主菜不重复
        dinner_idx = variant
        if "尿酸" in tags and dinner_idx == 1:
            # 跳过海鲜晚餐(白灼虾仁,索引1),选用其它非海鲜变体
            safe_dinners = [i for i in range(7) if i != 1]
            dinner_idx = safe_dinners[variant % len(safe_dinners)]

        pools = {
            "breakfast": self._BREAKFAST_POOL[variant],
            "lunch": self._LUNCH_POOL[variant],
            "dinner": self._DINNER_POOL[dinner_idx],
            "snack": self._SNACK_POOL[variant],
        }
        ratios = {"breakfast": 0.28, "lunch": 0.38, "dinner": 0.26, "snack": 0.08}

        meals: List[Dict[str, Any]] = []
        for meal_type in ("breakfast", "lunch", "dinner", "snack"):
            dish_items = []
            for name, ing, method, cal, pro, carb, fat, fiber, tips in pools[meal_type]:
                scale = target / 1800.0
                dish_items.append(
                    {
                        "name": name,
                        "description": f"以{ing}为主要食材的营养搭配",
                        "ingredients": ing,
                        "cooking_method": method,
                        "calories": int(cal * scale),
                        "protein": round(pro * scale, 1),
                        "carbohydrate": round(carb * scale, 1),
                        "fat": round(fat * scale, 1),
                        "fiber": round(fiber * scale, 1),
                        "tips": tips,
                    }
                )
            meals.append(
                {
                    "meal_type": meal_type,
                    "meal_label": MEAL_LABELS[meal_type],
                    "target_calories": int(target * ratios[meal_type]),
                    "actual_calories": sum(d["calories"] for d in dish_items),
                    "dishes": dish_items,
                }
            )

        # 禁忌净化:命中任何 avoid 关键词的菜品替换为安全替身
        meals = self._sanitize_meals(meals, conditions, disliked | allergies)

        nutrition_info = {
            "calories": sum(m["actual_calories"] for m in meals),
            "protein": self._sum(meals, "protein"),
            "carbs": self._sum(meals, "carbohydrate"),
            "fat": self._sum(meals, "fat"),
            "fiber": self._sum(meals, "fiber"),
        }

        condition_tags = [c["tag"] for c in conditions]
        title = f"个性化营养食谱{'(' + '/'.join(condition_tags) + '调理)' if condition_tags else ''}"
        tips = [
            f"每日目标热量约 {target} kcal,可根据体重变化上下浮动 10%",
            "进餐顺序建议:蔬菜 → 蛋白质 → 主食,有助于控制餐后血糖",
            "每日饮水 1500~2000ml,食盐摄入控制在 5g 以内",
            "建议配合每周 150 分钟中等强度有氧运动",
        ]
        for c in conditions:
            tips.append(f"针对{c['tag']}问题:建议多摄入 {'、'.join(c['prefer'][:3])},避免 {'、'.join(c['avoid'][:2])}")

        if knowledge_snippets:
            top = (
                knowledge_snippets[0]
                if isinstance(knowledge_snippets[0], dict)
                else {"content": str(knowledge_snippets[0])}
            )
            head = (
                f"【{top.get('source', '')}·{top.get('evidence_level', '')}级证据】"
                if top.get("source")
                else "【营养学依据】"
            )
            tips.append(f"{head}:{(top.get('content') or '')[:80]}...")

        blocked = disliked | allergies
        if blocked:
            tips.append(f"已规避您标注的忌口/过敏食材:{'、'.join(sorted(blocked))}")

        return {
            "name": title,
            "description": (
                f"根据您的体检指标({parsed_metrics.get('summary', '')}),"
                f"结合每日约 {target} kcal 的能量需求,生成的营养均衡膳食方案。"
                "全方案遵循低GI、低盐、低脂原则,粗细搭配、荤素均衡。"
            ),
            "nutrition_info": nutrition_info,
            "total_calories": nutrition_info["calories"],
            "meals": meals,
            "tips": tips,
            "template": True,
        }

    @staticmethod
    def _sanitize_meals(
        meals: List[Dict[str, Any]],
        conditions: List[Dict[str, Any]],
        blocked: set,
    ) -> List[Dict[str, Any]]:
        """把命中禁忌关键词的菜品替换为安全替身(避免规则引擎产出违禁食材)"""
        avoid = set()
        for c in conditions:
            for b in c.get("avoid") or []:
                if b:
                    avoid.add(b)
        avoid |= {b for b in blocked if b}
        if not avoid:
            return meals

        name, ing, method, cal, pro, carb, fat, fiber, tips = RecipeGenerator._SAFE_DISH
        safe_dish = {
            "name": name,
            "description": f"以{ing}为主要食材的营养搭配",
            "ingredients": ing,
            "cooking_method": method,
            "calories": cal,
            "protein": pro,
            "carbohydrate": carb,
            "fat": fat,
            "fiber": fiber,
            "tips": tips,
        }
        for m in meals:
            new_dishes = []
            for d in m.get("dishes") or []:
                # 仅按菜品名 + 食材判定禁忌(描述性文字如"替代白粥"不算违规)
                text = " ".join(
                    str(d.get(k) or "") for k in ("name", "ingredients")
                )
                if any(k and k in text for k in avoid):
                    new_dishes.append(dict(safe_dish))
                else:
                    new_dishes.append(d)
            m["dishes"] = new_dishes
            m["actual_calories"] = sum(d["calories"] for d in new_dishes)
        return meals

    # ------------------------------------------------------------- 审核规则
    def rule_review(
        self,
        recipe: Dict[str, Any],
        parsed_metrics: Dict[str, Any],
        target_calories: int,
    ) -> Dict[str, Any]:
        """基于规则的食谱审核(不依赖 LLM)

        注意:只检查「真实菜品名 + 食材 + 菜品描述」,不检查 dietary tips,
        否则"避免含糖饮料"这类建议文本会被误判为违规食材。
        """
        issues: List[str] = []

        # 仅抽取真实食物内容(菜品名 + 食材)用于禁忌校验;
        # 不扫描 description,否则"替代白粥""少盐"等描述性文字会被误判为违规食材
        dish_parts: List[str] = []
        for meal in recipe.get("meals") or []:
            for dish in meal.get("dishes") or []:
                dish_parts.extend(
                    [
                        str(dish.get("name") or ""),
                        str(dish.get("ingredients") or ""),
                    ]
                )
        dish_text = " ".join(dish_parts)

        total = recipe.get("total_calories", 0)
        if total and not (target_calories * 0.75 <= total <= target_calories * 1.25):
            issues.append(
                f"总热量 {total} kcal 偏离目标 {target_calories} kcal 超过 25%,需要调整份量"
            )

        for condition in self._match_conditions(parsed_metrics):
            for bad in condition["avoid"]:
                if bad and bad in dish_text:
                    issues.append(f"检测到与「{condition['tag']}」相冲突的食材:{bad}")

        if not recipe.get("meals"):
            issues.append("食谱未包含任何餐次安排")

        return {
            "passed": not issues,
            "issues": issues,
            "summary": "食谱通过营养审核。" if not issues else "；".join(issues),
        }

    # ------------------------------------------------------------- 工具方法
    @staticmethod
    def _match_conditions(parsed_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        tags_text = " ".join(parsed_metrics.get("risk_tags") or [])
        tags_text += " " + str(parsed_metrics.get("summary") or "")
        matched = []
        for rule in CONDITION_RULES:
            if any(kw in tags_text for kw in rule["keywords"]):
                matched.append(rule)
        return matched

    @staticmethod
    def _as_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return "、".join(str(v) for v in value)
        return str(value)

    @staticmethod
    def _as_int(value: Any) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _as_float(value: Any) -> float:
        try:
            return round(float(value), 1)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _sum(meals: List[Dict[str, Any]], field: str) -> float:
        return round(sum(d.get(field, 0) for m in meals for d in m.get("dishes", [])), 1)
