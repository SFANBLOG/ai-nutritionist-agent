"""AI Agent 工作流模块(LangGraph 多 Agent 协作)

工作流拓扑:
    健康分析 → 营养规划 → 食谱生成 → 质量审核
                                        ├── 审核通过 → END
                                        └── 审核不通过 → 回到「食谱生成」重做
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.services.health_report_parser import HealthReportParser
from app.services.knowledge_base import KnowledgeBase, get_knowledge_base
from app.services.recipe_generator import MEAL_LABELS, RecipeGenerator

logger = logging.getLogger(__name__)


class NutritionState(TypedDict, total=False):
    """Agent 工作流状态"""

    # 输入
    report_content: str
    parsed_metrics: Dict[str, Any]
    user_profile: Dict[str, Any]
    preferences: List[Dict[str, Any]]

    # 中间产物
    health_analysis: str
    knowledge_snippets: List[str]
    nutrition_plan: str
    target_calories: int

    # 多日菜单 / HITL 透传字段(必须声明,否则 LangGraph 状态通道会丢弃)
    day_index: int
    extra_instruction: str
    awaiting_human: bool

    # 输出
    recipe: Dict[str, Any]
    review_result: Dict[str, Any]
    review_passed: bool
    iteration_count: int
    revision_notes: List[str]
    llm_enabled: bool
    log: List[str]


# --------------------------------------------------------------------------
# 提示词
# --------------------------------------------------------------------------
_HEALTH_ANALYSIS_PROMPT = """你是一位专业的健康分析师,擅长解读体检报告。
请根据用户体检指标,输出一段结构化的健康分析,需包含:
1) 各项指标解读与分级(正常/偏高/偏低);
2) 潜在健康风险评估;
3) 饮食层面最需要关注的 2~3 个点。
要求语言专业、通俗易懂,控制在 400 字以内,不要输出 Markdown 表格。"""

_NUTRITION_PLAN_PROMPT = """你是一位资深临床营养师。
请结合健康分析结论与检索到的营养学知识,制定个性化营养方案,需包含:
1) 每日总热量目标与三大营养素供能比(碳水/蛋白质/脂肪);
2) 需要重点限制的食物类别;
3) 推荐优先摄入的食物类别;
4) 三餐能量分配建议。
控制在 500 字以内,语言简洁专业。"""

_RECIPE_PROMPT = """你是一位专业厨师兼注册营养师。
请严格以 JSON 格式输出一份一日食谱,不要输出任何 JSON 以外的解释文字。
JSON 结构如下:
{
  "name": "食谱名称",
  "description": "食谱整体说明(80字以内)",
  "meals": [
    {
      "meal_type": "breakfast | lunch | dinner | snack",
      "target_calories": 500,
      "dishes": [
        {
          "name": "菜品名称",
          "description": "菜品简介",
          "ingredients": "食材及用量",
          "cooking_method": "烹饪方法",
          "calories": 300,
          "protein": 12.5,
          "carbohydrate": 40.0,
          "fat": 8.0,
          "fiber": 5.0,
          "tips": "健康提示"
        }
      ]
    }
  ],
  "tips": ["饮食建议1", "饮食建议2"]
}
要求:包含早餐/午餐/晚餐,可含 1 次加餐;每餐 1~3 道菜;营养素单位分别为 kcal 与 g;
必须完全规避用户忌口与过敏食材,并符合其健康状况的饮食禁忌。"""

_REVIEW_PROMPT = """你是一位资深注册营养师,负责审核食谱质量。
请从「营养均衡性、与健康状况的匹配度、食材禁忌、热量合理性」四个维度审核,
如果完全合格,请以 "PASS" 开头回答;否则以 "FAIL" 开头,并简要列出需要修改的具体问题。
回答控制在 200 字以内。"""


class NutritionAgentWorkflow:
    """营养师 Agent 工作流"""

    def __init__(
        self,
        knowledge_base: Optional[KnowledgeBase] = None,
        llm: Any = None,
        human_gate: bool = False,
    ):
        self.generator = RecipeGenerator()
        self.parser = HealthReportParser()
        self.knowledge_base = knowledge_base or get_knowledge_base()
        self.llm = llm if llm is not None else self._build_llm()
        self.human_gate = human_gate
        self.workflow = self._build_workflow()

    # ------------------------------------------------------------------ 构建
    def _build_llm(self):
        if not settings.llm_configured:
            logger.warning("未配置可用的 LLM API Key,Agent 将使用规则引擎模式运行")
            return None
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=settings.LLM_MODEL,
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                temperature=settings.LLM_TEMPERATURE,
                timeout=settings.LLM_TIMEOUT,
                max_retries=1,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("LLM 初始化失败,回退规则引擎模式: %s", exc)
            return None

    def _chat(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """统一的 LLM 调用封装,失败返回 None"""
        if self.llm is None:
            return None
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            resp = self.llm.invoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
            )
            content = getattr(resp, "content", "")
            if isinstance(content, list):  # 部分模型返回多段内容
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            return (content or "").strip() or None
        except Exception as exc:
            logger.warning("LLM 调用失败,使用规则引擎兜底: %s", exc)
            return None

    def _build_workflow(self) -> Any:
        workflow = StateGraph(NutritionState)

        workflow.add_node("health_analysis", self._health_analysis_agent)
        workflow.add_node("nutrition_planning", self._nutrition_planning_agent)
        workflow.add_node("recipe_generation", self._recipe_generation_agent)
        workflow.add_node("quality_review", self._quality_review_agent)

        workflow.set_entry_point("health_analysis")
        workflow.add_edge("health_analysis", "nutrition_planning")
        workflow.add_edge("nutrition_planning", "recipe_generation")
        workflow.add_edge("recipe_generation", "quality_review")
        if self.human_gate:
            # HITL 闸门开启:审核节点产出结果后交由人工决策,不再自动回边重做
            # (避免无人工介入时无限重试;人工可在界面「请求修订」触发受控重做)
            workflow.add_edge("quality_review", END)
        else:
            workflow.add_conditional_edges(
                "quality_review",
                self._should_revise,
                {"revise": "recipe_generation", "complete": END},
            )
        return workflow.compile()

    # ------------------------------------------------------------------ 节点
    def _health_analysis_agent(self, state: NutritionState) -> Dict[str, Any]:
        """健康分析 Agent:解读体检指标,评估健康状况"""
        metrics = state.get("parsed_metrics") or {}
        fallback = self._fallback_health_analysis(metrics)
        user_prompt = (
            f"体检指标明细(JSON):{json.dumps(metrics, ensure_ascii=False)}\n"
            f"体检报告原文:{state.get('report_content') or '无'}\n"
            f"用户基础信息:{json.dumps(state.get('user_profile') or {}, ensure_ascii=False, default=str)}"
        )
        analysis = self._chat(_HEALTH_ANALYSIS_PROMPT, user_prompt) or fallback
        return {
            "health_analysis": analysis,
            "iteration_count": 0,
            "llm_enabled": self.llm is not None,
            "log": (state.get("log") or []) + ["健康分析 Agent 完成"],
        }

    def _nutrition_planning_agent(self, state: NutritionState) -> Dict[str, Any]:
        """营养规划 Agent:结合知识库制定营养方案"""
        health_analysis = state.get("health_analysis", "")
        metrics = state.get("parsed_metrics") or {}
        preferences = state.get("preferences") or []
        profile = state.get("user_profile") or {}

        query = f"{health_analysis} {metrics.get('summary', '')} 饮食建议"
        snippets: List[Dict[str, Any]] = []
        try:
            for item in self.knowledge_base.search(query, n_results=4):
                meta = item.get("metadata") or {}
                snippets.append(
                    {
                        "content": item["content"],
                        "source": meta.get("source", ""),
                        "evidence_level": meta.get("evidence_level", ""),
                        "category": meta.get("category", ""),
                    }
                )
        except Exception as exc:  # pragma: no cover
            logger.warning("知识库检索失败: %s", exc)

        target_calories = self.generator.estimate_target_calories(profile)
        pref_text = "；".join(
            f"{p.get('preference_type')}:{p.get('preference_value')}" for p in preferences
        ) or "无特殊偏好"

        user_prompt = (
            f"健康分析:{health_analysis}\n\n"
            f"检索到的营养学知识:\n"
            + "\n---\n".join(self._render_snippet(s) for s in snippets)
            + "\n\n"
            f"用户偏好:{pref_text}\n"
            f"每日目标热量参考:{target_calories} kcal"
        )
        plan = self._chat(_NUTRITION_PLAN_PROMPT, user_prompt) or self._fallback_plan(
            metrics, snippets, target_calories
        )
        return {
            "nutrition_plan": plan,
            "knowledge_snippets": snippets,
            "target_calories": target_calories,
            "log": (state.get("log") or []) + [f"营养规划 Agent 完成(知识库召回 {len(snippets)} 条)"],
        }

    def _recipe_generation_agent(self, state: NutritionState) -> Dict[str, Any]:
        """食谱生成 Agent:输出结构化食谱(支持按审核意见返工 / 按天多样性 / 人工修订意见)"""
        metrics = state.get("parsed_metrics") or {}
        profile = state.get("user_profile") or {}
        preferences = state.get("preferences") or []
        snippets = state.get("knowledge_snippets") or []
        revision_notes = state.get("revision_notes") or []
        extra_instruction = state.get("extra_instruction") or ""
        target_calories = state.get("target_calories") or self.generator.estimate_target_calories(profile)

        recipe: Optional[Dict[str, Any]] = None
        if self.llm is not None:
            user_prompt = (
                f"健康分析:{state.get('health_analysis', '')}\n\n"
                f"营养方案:{state.get('nutrition_plan', '')}\n\n"
                f"用户偏好:{json.dumps(preferences, ensure_ascii=False, default=str)}\n"
                f"每日目标热量:{target_calories} kcal\n"
                f"知识库要点:\n"
                + "\n".join(self._render_snippet(s)[:200] for s in snippets[:3])
            )
            if extra_instruction:
                user_prompt += f"\n\n{extra_instruction}"
            if revision_notes:
                user_prompt += "\n\n上一版食谱审核未通过,请务必修正以下问题:\n- " + "\n- ".join(revision_notes)
            raw = self._chat(_RECIPE_PROMPT, user_prompt)
            data = self.generator.extract_json(raw) if raw else None
            if data:
                recipe = self.generator.normalize(data)

        if recipe is None or not recipe.get("meals"):
            day_index = int(state.get("day_index", 0) or 0)
            recipe = self.generator.build_template_recipe(
                metrics, profile, preferences, snippets, day_index=day_index
            )

        return {
            "recipe": recipe,
            "log": (state.get("log") or [])
            + [f"食谱生成 Agent 完成(第 {state.get('iteration_count', 0) + 1} 版)"],
        }

    def _quality_review_agent(self, state: NutritionState) -> Dict[str, Any]:
        """质量审核 Agent:审核食谱合理性"""
        recipe = state.get("recipe") or {}
        metrics = state.get("parsed_metrics") or {}
        target_calories = state.get("target_calories") or 1800

        rule_result = self.generator.rule_review(recipe, metrics, target_calories)
        issues = list(rule_result["issues"])

        llm_verdict = self._chat(
            _REVIEW_PROMPT,
            f"健康分析:{state.get('health_analysis', '')}\n\n"
            f"体检指标:{json.dumps(metrics, ensure_ascii=False)}\n\n"
            f"待审核食谱(JSON):{json.dumps(recipe, ensure_ascii=False)[:4000]}",
        )
        if llm_verdict:
            if "PASS" not in llm_verdict.upper():
                issues.append(llm_verdict)
        elif not rule_result["passed"]:
            issues = rule_result["issues"]

        iteration = int(state.get("iteration_count", 0)) + 1
        passed = not issues
        forced_pass = False
        if not passed and iteration >= settings.MAX_REVIEW_ITERATIONS:
            # 达到最大重试次数,带风险提示放行,避免工作流死循环
            passed = True
            forced_pass = True

        awaiting_human = bool(self.human_gate)
        verdict = "通过" if passed else "不通过"
        log_msg = f"质量审核 Agent 第 {iteration} 轮:{verdict}"
        if awaiting_human:
            log_msg += "(待人工确认)"

        return {
            "review_result": {
                "passed": passed,
                "forced_pass": forced_pass,
                "issues": issues,
                "iteration": iteration,
                "llm_verdict": llm_verdict or "（规则引擎审核）",
                "rule_summary": rule_result["summary"],
                "awaiting_human": awaiting_human,
            },
            "review_passed": passed,
            # HITL 闸门开启时不自动回边:以 awaiting_human 标记,由人工决定后续
            "awaiting_human": awaiting_human,
            "iteration_count": iteration,
            "revision_notes": issues,
            "log": (state.get("log") or []) + [log_msg],
        }

    def _should_revise(self, state: NutritionState) -> str:
        """条件边:判断是否需要退回重做"""
        if state.get("review_passed"):
            return "complete"
        if int(state.get("iteration_count", 0)) >= settings.MAX_REVIEW_ITERATIONS:
            return "complete"
        return "revise"

    # ------------------------------------------------------------------ 兜底
    def _fallback_health_analysis(self, metrics: Dict[str, Any]) -> str:
        indicators = metrics.get("indicators") or []
        if not indicators:
            return "未从体检报告中解析到标准指标,建议补充完整报告后重新分析。"
        lines = ["【体检指标解读】"]
        for item in indicators:
            level = item.get("level", "-")
            mark = "✔" if level == "正常" else "⚠"
            lines.append(
                f"{mark} {item['name']}:{item['value']}{item.get('unit', '')}"
                f"(参考 {item.get('reference', '-')},评估:{level})"
            )
        abnormal = [i for i in indicators if i.get("level") != "正常"]
        lines.append("\n【饮食关注重点】")
        if abnormal:
            for item in abnormal[:3]:
                lines.append(f"· {item['name']}({item['level']}):{item.get('advice', '')}")
        else:
            lines.append("· 各项指标正常,建议保持均衡饮食、规律作息与适量运动。")
        return "\n".join(lines)

    def _fallback_plan(
        self, metrics: Dict[str, Any], snippets: List[str], target_calories: int
    ) -> str:
        lines = [
            f"【每日能量目标】约 {target_calories} kcal",
            "【三大营养素供能比】碳水化合物 50%~55%,蛋白质 15%~20%,脂肪 25%~30%",
            "【三餐能量分配】早餐 30%、午餐 40%、晚餐 30%",
        ]
        conditions = _match_condition_tags(metrics)
        if conditions:
            lines.append(f"【重点关注】{'、'.join(conditions)}相关饮食调理")
        if snippets:
            lines.append("【营养学依据】")
            for s in snippets[:3]:
                head = (
                    f"{s.get('source', '')}（{s.get('evidence_level', '')}级证据）"
                    if s.get("source")
                    else "营养学依据"
                )
                lines.append(f"· {head}:{(s.get('content') or '')[:120]}")
        lines.append("【基本原则】少盐少油控糖、粗细搭配、荤素均衡、定时定量。")
        return "\n".join(lines)

    # ------------------------------------------------------------------ 工具
    @staticmethod
    def _render_snippet(snippet: Dict[str, Any]) -> str:
        """把结构化知识片段渲染为带来源与证据等级的文本(供注入 LLM / 兜底方案)"""
        content = snippet.get("content") or ""
        source = snippet.get("source") or ""
        level = snippet.get("evidence_level") or ""
        if not source:
            return content
        tag = f"【{source}" + (f"·{level}级证据】" if level else "】")
        return f"{tag} {content}"

    # ------------------------------------------------------------------ 运行
    def run(
        self,
        health_report: Any = None,
        preferences: Optional[List[Any]] = None,
        user_info: Any = None,
        report_content: Optional[str] = None,
        parsed_metrics: Optional[Dict[str, Any]] = None,
        user_profile: Optional[Dict[str, Any]] = None,
        preference_dicts: Optional[List[Dict[str, Any]]] = None,
        day_index: int = 0,
        extra_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """运行 Agent 工作流,返回完整执行结果

        day_index: 多日菜单中当天序号(0 起),用于模板轮换与 LLM 多样性提示
        extra_instruction: 注入食谱生成环节的额外指令(如多日轮换 / 人工修订意见)
        """
        # 兼容两种入参:ORM 对象(旧签名) 与 纯 dict(推荐)
        if health_report is not None:
            content = getattr(health_report, "report_content", None) or report_content or ""
            metrics = getattr(health_report, "analysis_result", None) or parsed_metrics
        else:
            content = report_content or ""
            metrics = parsed_metrics or {}

        if not metrics:
            metrics = self.parser.parse(content or "")

        if user_profile is None:
            if user_info is not None:
                user_profile = _orm_to_profile(user_info)
            else:
                user_profile = {}

        if preference_dicts is None:
            preference_dicts = []
            for p in preferences or []:
                if isinstance(p, dict):
                    preference_dicts.append(p)
                else:
                    preference_dicts.append(
                        {
                            "preference_type": getattr(p, "preference_type", ""),
                            "preference_value": getattr(p, "preference_value", ""),
                        }
                    )

        initial: NutritionState = {
            "report_content": content,
            "parsed_metrics": metrics,
            "user_profile": user_profile,
            "preferences": preference_dicts,
            "day_index": day_index,
            "extra_instruction": extra_instruction or "",
            "log": [],
        }
        result = dict(self.workflow.invoke(initial))
        result.setdefault("recipe", {})
        return result


# --------------------------------------------------------------------------
def _orm_to_profile(user: Any) -> Dict[str, Any]:
    """把 User ORM 对象转换为普通字典"""
    return {
        "username": getattr(user, "username", None),
        "age": getattr(user, "age", None),
        "gender": getattr(getattr(user, "gender", None), "value", getattr(user, "gender", None)),
        "height": getattr(user, "height", None),
        "weight": getattr(user, "weight", None),
    }


def _match_condition_tags(metrics: Dict[str, Any]) -> List[str]:
    text = " ".join(metrics.get("risk_tags") or []) + " " + str(metrics.get("summary") or "")
    tags = []
    for kw, tag in (("血糖", "血糖"), ("血压", "血压"), ("尿酸", "尿酸"), ("胆固醇", "血脂"),
                    ("甘油三酯", "血脂")):
        if kw in text and tag not in tags:
            tags.append(tag)
    return tags


__all__ = ["NutritionAgentWorkflow", "NutritionState", "MEAL_LABELS"]
