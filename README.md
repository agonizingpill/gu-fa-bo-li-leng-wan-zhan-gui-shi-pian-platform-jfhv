# 古法玻璃冷弯展柜试片台

棠镜玻璃试制组保留每次冷却后的实弯读数，根据材料交互修订曲线并安排唯一试制机位。

## 现场工作与联系人

模拟客户为棠镜玻璃试制组。夹具登记、温区试片、交互项比较、打样委托；夹具有效行程不足拒排且不占机位。

- 弯模与行程 `jigs`，字段为 `spread`（台面跨度 mm）、`max_throw`（最大行程 mm）、`calibrated`（量具在校）。模型约束位于 `backend/domain/jigs_model.py`，规则位于 `jigs_service.py`。
- 温区试片 `coupons`，字段为 `jig`（弯模）、`heat`（保温温度 °C）、`thick`（片厚 mm）、`target`（目标弯度 mm）、`measured`（冷却弯度 mm）、`measured_original`（首次更正前的原始读数）、`revision_note`（更正说明）、`locked`（已确认）。每次读数更正追加到不可变流水 `coupon_revisions`。模型约束位于 `backend/domain/coupons_model.py`，规则位于 `coupons_service.py`。
- 预测曲线签注 `profiles`，字段为 `coupon`（基准试片）、`prediction`（拟合弯度 mm）、`mae`（留出 MAE mm）、`curve`（改善说明）、`token`（拟合编号）、`voided`（已失效）、`void_reason`（失效原因）。模型约束位于 `backend/domain/profiles_model.py`，规则位于 `profiles_service.py`。
- 试制工位委托 `work_orders`，字段为 `profile`（依据）、`jig`（工位弯模）、`slot`（机位时段，暂停时置空释放）、`quantity`（试片数）、`state`（状态）。模型约束位于 `backend/domain/work_orders_model.py`，规则位于 `work_orders_service.py`。

团队为模拟的6 人打样组，负责展柜旧式玻璃的冷弯样件。

试制员分开记尺规、片厚和热区读数。换夹具后有效行程容易漏核，两个参数的互相影响难从单列趋势看出，打样回执难追到原试片。

夹具检定和历史试片进入比较工作台，打样师领取附试片依据的委托单。

### 一天的业务操作

1. 08:35 在 CL-08 上校验量具，记录 25 mm 行程。
2. 09:10 用 CL-44 测量 GP-NEW 的 4 mm 玻璃冷却弯度 8.4 mm。
3. 10:20 复核员查验尺规并确认 GP-NEW。
4. 10:40 见证后发现 GP-12 冷却弯度抄错，复核员更正为 8.1 mm，原读数 7.6 mm 留痕；PRO-11 同步失效，JOB-21 暂停并释放机位。
5. 11:10 以 0.035 正则强度计算温区拟合。
6. 13:00 签注 PRO-24，核对留出误差；排队期间读数被更正的旧任务被拒绝签注。
7. 14:10 CL-18 有效行程不足，拒绝机位委托；换用 CL-44。
8. 16:20 核对 W-0302 完成打样，已打样委托仍可回看原依据。

## 启动

```sh
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

打开 `http://127.0.0.1:18306`。FastAPI OpenAPI 在 `http://127.0.0.1:19306/docs`。
Compose 运行 Nginx、Python FastAPI、独立 Redis 消费进程、SQL 数据库和 Redis，SQL 与 Redis 使用命名卷。
本机开发时，在 Python 3.11 环境安装 `backend/requirements.txt` 后从 backend 目录运行 `uvicorn core.app:app`。须提供 `DATABASE_URL`、`REDIS_URL`、`JWT_SECRET`，`SEED_DEMO` 控制演示初始化。

| 演示账号 | 权限 |
|---|---|
| operator@demo.test | 提交领域记录和计算请求 |
| reviewer@demo.test | 提交记录并执行有业务约束的复核操作 |
| viewer@demo.test | 浏览业务台账 |

三个本地演示账号均使用 `DemoC0de!2026`。角色在 `backend/core/roles.py` 和 `frontend/src/store.js` 中声明。计算状态在 worker、queueing、API 和同一前端 store 中使用。

## 页面与接口

| 业务任务 | FastAPI 路由 | 页面 |
|---|---|---|
| 弯模与行程 | `/jigs` /jigs/calibrate | `frontend/src/pages/jigs.js` |
| 温区试片 | `/coupons`、/coupons/record-coupon、/coupons/witness、/coupons/correct-measured、/coupons/{code}/revisions | `frontend/src/pages/coupons.js` |
| 预测曲线签注 | `/profiles`、/profiles/fit-curve、/profiles/sign-profile、/profiles/void-orphan | `frontend/src/pages/profiles.js` |
| 试制工位委托 | `/work_orders`、/work_orders/book-jig、/work_orders/complete、/work_orders/{order}/basis | `frontend/src/pages/work_orders.js` |

## 读数更正与失效联动

试片经尺规见证后，若发现冷却弯度抄错，由复核员在试片页发起更正（`/coupons/correct-measured`），规则如下：

1. **保留原读数**：首次更正把原读数固化到 `measured_original`，每次更正向 `coupon_revisions` 追加一条不可变流水（更正前后读数、原因、操作人、时间），后续更正不会覆盖原始值。
2. **曲线同步作废**：以该试片为基准的曲线在同一数据库事务内置 `voided`。失效曲线在 `/work_orders/book-jig` 被直接拒绝，且拒绝时不占用机位。
3. **排队拟合拒绝签注**：拟合任务在 Redis 队列中保存的是发起时的试片快照；签注时若当前读数与快照读数不一致，即使任务已算完也返回 409，须重新发起拟合。
4. **委托暂停与机位释放同事务生效**：引用失效曲线且状态为「待打样」的委托置为「已暂停（曲线失效）」并把 `slot` 置空，原时段可被新委托重新占用；「已打样」委托状态与时段不变，仍可通过 `/work_orders/{order}/basis` 查到原曲线与试片依据。
5. **并发一致性**：更正先对试片行加 `FOR UPDATE` 行锁，曲线作废与机位释放随后在同一事务内完成；与签注、排位并发时，要么全部可见要么全部回滚。
6. **无源旧曲线**：基准试片已无法追溯的旧曲线，复核员通过 `/profiles/void-orphan` 按失效处理。

既有数据库启动时由 `backend/core/migrate.py` 幂等补列并放开 `work_orders.slot` 的 NOT NULL，无需手工迁移。后端测试在 `backend/tests`，用 SQLite 内存库与 fakeredis 运行：`python -m pytest`。

SQL 实体与约束在 `backend/domain` 下维护。前端使用原生 ES modules。核心算子为 PolynomialFeatures + Lasso。算法按温度排序每四条留出一条；训练拟合二次多项式和标准化。报告使用 mm 和可复现特征系数。

数据为模拟试制记录。工单留在本地数据库供核查。

[MIT](LICENSE)
