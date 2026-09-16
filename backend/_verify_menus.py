"""离线功能验证:多日菜单落库 + HITL 人工确认闸门(无外部服务依赖)"""
import os
import sys
import tempfile
from datetime import date, timedelta

# 离线模式:避免 BGE 模型联网重试浪费时间
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

# 使用全新临时 SQLite,避免状态污染
tmp_db = os.path.join(tempfile.gettempdir(), f"verify_menus_{os.getpid()}.db")
if os.path.exists(tmp_db):
    os.remove(tmp_db)

os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db}"
os.environ["HUMAN_REVIEW_GATE"] = "true"
os.environ["VECTOR_DB_TYPE"] = "memory"
os.environ["MINIO_ENDPOINT"] = ""

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app.main as main_mod  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

passed = 0
failed = 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[PASS] {name} {extra}")
    else:
        failed += 1
        print(f"[FAIL] {name} {extra}")


with TestClient(main_mod.app) as client:
    H = {}

    # 1) 健康检查应包含 human_review_gate
    r = client.get("/api/health")
    check("health 含 human_review_gate", r.status_code == 200 and r.json().get("human_review_gate") is True,
          f"gate={r.json().get('human_review_gate')}")

    # 2) 注册 + 登录
    u = f"menuuser{os.getpid()}"
    r = client.post("/api/auth/register", json={"username": u, "email": f"{u}@x.com", "password": "pw123456", "full_name": "菜单"})
    check("注册", r.status_code == 200, f"code={r.status_code} body={str(r.text)[:120]}")
    token = None
    if r.status_code == 200:
        lr = client.post("/api/auth/login", data={"username": u, "password": "pw123456"})
        if lr.status_code == 200:
            token = lr.json().get("access_token")
    check("登录获取 token", bool(token))
    H = {"Authorization": f"Bearer {token}"}

    # 3) 上传体检报告
    report = """空腹血糖:7.4 mmol/L
血压:148/95 mmHg
尿酸:486 μmol/L
总胆固醇:6.3 mmol/L
甘油三酯:2.6 mmol/L"""
    r = client.post("/api/health-reports/", json={"report_name": "多日验证报告", "report_content": report}, headers=H)
    check("上传报告", r.status_code == 200, f"code={r.status_code}")
    hr_id = r.json().get("id") if r.status_code == 200 else None
    check("报告解析出异常指标", bool(hr_id) and (r.json().get("analysis_result", {}).get("abnormal_count", 0) > 0),
          f"abnormal={r.json().get('analysis_result', {}).get('abnormal_count') if r.status_code == 200 else '-'}")

    # 4) 生成 3 天多日菜单
    r = client.post("/api/recipes/generate", json={"health_report_id": hr_id, "days": 3}, headers=H)
    check("生成多日食谱", r.status_code == 200, f"code={r.status_code} body={str(r.text)[:200]}")
    rid = None
    if r.status_code == 200:
        rec = r.json()
        rid = rec["id"]
        check("返回嵌套 menus", isinstance(rec.get("menus"), list) and len(rec.get("menus", [])) == 3, f"days={len(rec.get('menus', []))}")
        check("状态为待人工确认", rec["status"] == "pending_review", f"status={rec['status']}")
        check("review_status=pending", rec["review_status"] == "pending")
        check("days 字段=3", rec["days"] == 3)
        lunches = []
        for m in rec["menus"]:
            lunch = next((meal for meal in m["meals"] if meal["meal_type"] == "lunch"), None)
            if lunch:
                lunches.append(tuple(d["name"] for d in lunch["dishes"]))
        check("相邻天午餐主菜不同", len(set(lunches)) >= 2, f"lunches={lunches}")
        all_dishes = " ".join(d["name"] + (d["ingredients"] or "") for m in rec["menus"] for meal in m["meals"] for d in meal["dishes"])
        check("禁忌净化:无虾仁/海鲜违禁", "虾仁" not in all_dishes, f"命中={'虾仁' in all_dishes}")

        from app.core.database import SessionLocal
        from app.models.recipe import DailyMenu, Meal, Dish
        db = SessionLocal()
        try:
            dm = db.query(DailyMenu).filter(DailyMenu.recipe_id == rid).count()
            ml = db.query(Meal).join(DailyMenu).filter(DailyMenu.recipe_id == rid).count()
            ds = db.query(Dish).join(Meal).join(DailyMenu).filter(DailyMenu.recipe_id == rid).count()
            check("daily_menus 落库 3 行", dm == 3, f"dm={dm}")
            check("meals 落库(3天*4餐=12)", ml == 12, f"ml={ml}")
            check("dishes 落库>0", ds > 0, f"ds={ds}")
            dates = sorted(str(m.menu_date) for m in db.query(DailyMenu).filter(DailyMenu.recipe_id == rid))
            check("起始日期连续3天", dates == [str(date.today() + timedelta(days=i)) for i in range(3)], f"dates={dates}")
        finally:
            db.close()

        # 6) 获取菜单明细端点
        r2 = client.get(f"/api/recipes/{rid}/menus", headers=H)
        check("GET /menus 返回 3 天", r2.status_code == 200 and len(r2.json()) == 3, f"code={r2.status_code}")

        # 7) HITL: 确认采用
        r3 = client.post(f"/api/recipes/{rid}/review/approve", json={"decision": "通过"}, headers=H)
        check("确认采用 -> active", r3.status_code == 200 and r3.json()["status"] == "active" and r3.json()["review_status"] == "approved",
              f"status={r3.json().get('status') if r3.status_code == 200 else r3.status_code}")

        # 8) 再生成并请求修订(重做)
        r4 = client.post("/api/recipes/generate", json={"health_report_id": hr_id, "days": 2}, headers=H)
        rid2 = r4.json()["id"] if r4.status_code == 200 else None
        check("再生成2天待确认", r4.status_code == 200 and r4.json()["status"] == "pending_review", f"code={r4.status_code}")
        r5 = client.post(f"/api/recipes/{rid2}/review/request-revision", json={"notes": "午餐热量偏高,请降低主食份量并增加蔬菜"}, headers=H)
        ok = r5.status_code == 200 and r5.json()["status"] == "pending_review" and r5.json()["revision_count"] == 1
        check("请求修订 -> 重做后仍待确认(rc=1)", ok,
              f"status={r5.json().get('status') if r5.status_code == 200 else r5.status_code} rc={r5.json().get('revision_count') if r5.status_code == 200 else '-'}")
        if r5.status_code == 200:
            check("修订后天数仍为2", r5.json()["days"] == 2, f"days={r5.json()['days']}")
            from app.core.database import SessionLocal
            from app.models.recipe import DailyMenu
            db = SessionLocal()
            try:
                dm2 = db.query(DailyMenu).filter(DailyMenu.recipe_id == rid2).count()
                check("修订后 daily_menus 仍为 2 行", dm2 == 2, f"dm={dm2}")
            finally:
                db.close()

    # 9) 关闭闸门时直接生效(直接调用 service 验证 gate=False 行为)
    from app.core.database import SessionLocal
    from app.models.user import User
    from app.models.health_report import HealthReport
    from app.services.menu_service import generate_and_persist
    db = SessionLocal()
    try:
        usr = db.query(User).filter(User.username == u).first()
        hr = db.query(HealthReport).filter_by(id=hr_id).first()
        out = generate_and_persist(db, user=usr, health_report=hr, preferences=[], days=1, human_gate=False)
        check("gate=false 时直接 active", out["status"] == "active", f"status={out['status']}")
    finally:
        db.close()

print(f"\n==== 结果: {passed} 通过 / {failed} 失败 ====")
if os.path.exists(tmp_db):
    os.remove(tmp_db)
sys.exit(1 if failed else 0)
