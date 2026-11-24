import threading

import pytest
from sqlalchemy import create_engine, event, select

import core.db as db
from core.db import transaction
from domain.coupons_model import coupons
from domain.profiles_model import profiles
from domain.work_orders_model import work_orders
from tests.fixtures import world  # noqa: F401


def test_concurrent_corrections_serialize_and_leave_consistent_state(world):
    errors = []

    def correct(measured):
        try:
            resp = world.post('/coupons/correct-measured', json={
                'coupon': 'GP-12', 'measured': measured, 'reason': f'并发更正 {measured}'})
            if resp.status_code != 200:
                errors.append(resp.status_code)
        except Exception as exc:  # 连接级失败也算串行化冲突
            errors.append(repr(exc))

    threads = [threading.Thread(target=correct, args=(9.1,)),
               threading.Thread(target=correct, args=(9.7,))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with transaction() as conn:
        coupon = conn.execute(select(coupons).where(coupons.c.code == 'GP-12')).mappings().one()
        profile = conn.execute(select(profiles).where(profiles.c.code == 'PRO-A')).mappings().one()
        order = conn.execute(select(work_orders).where(
            work_orders.c.code == 'JOB-PENDING')).mappings().one()

    # 两次更正都被接受（串行执行），最终读数是其中之一
    assert not errors
    assert coupon['measured'] in (9.1, 9.7)
    assert coupon['measured_original'] == 8.6  # 原始读数始终不丢
    # 无论哪个事务后结束，曲线作废与机位释放都成对生效
    assert profile['voided'] is True
    assert order['state'] == '已暂停（曲线失效）'
    assert order['slot'] is None


@pytest.fixture()
def file_engine(tmp_path):
    """多连接文件库：WAL + busy timeout，模拟 Postgres 下的行锁等待。"""
    url = f'sqlite+pysqlite:///{tmp_path}/concurrency.db'
    engine = create_engine(url, connect_args={'timeout': 15, 'check_same_thread': False})

    @event.listens_for(engine, 'connect')
    def _wal(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute('PRAGMA journal_mode=WAL')
        cur.execute('PRAGMA busy_timeout=15000')
        cur.close()

    previous = db.engine
    db.engine = engine
    db.metadata.create_all(engine)
    yield engine
    db.engine = previous
    engine.dispose()


def test_correction_is_atomic_under_real_lock_contention(file_engine):
    from fastapi.testclient import TestClient
    from sqlalchemy import insert
    from core.app import app
    from core import auth
    from domain.jigs_model import jigs

    with transaction() as conn:
        conn.execute(insert(jigs).values(
            code='CL-44', spread=180, max_throw=32, calibrated=True))
        for i in range(2):
            conn.execute(insert(coupons).values(
                code=f'GP-{i:02d}', jig='CL-44', heat=410 + i, thick=2,
                target=10, measured=5.0, locked=True))
        conn.execute(insert(profiles).values(
            code='PRO-A', coupon='GP-01', prediction=9.0, mae=1.2,
            curve={}, token='tok-A', voided=False, void_reason=None))
        conn.execute(insert(work_orders).values(
            code='JOB-PENDING', profile='PRO-A', jig='CL-44',
            slot='11-25 09:00', quantity=2, state='待打样'))

    app.dependency_overrides[auth.actor] = lambda: {'sub': 'reviewer@demo.test', 'role': 'reviewer'}
    barrier = threading.Barrier(2)
    outcomes = []

    def use_client(measured):
        with TestClient(app) as client:
            barrier.wait()
            outcomes.append(client.post('/coupons/correct-measured', json={
                'coupon': 'GP-01', 'measured': measured, 'reason': f'竞争 {measured}'}).status_code)

    threads = [threading.Thread(target=use_client, args=(6.1,)),
               threading.Thread(target=use_client, args=(6.7,))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    app.dependency_overrides.clear()

    assert outcomes == [200, 200]
    with transaction() as conn:
        order = conn.execute(select(work_orders).where(
            work_orders.c.code == 'JOB-PENDING')).mappings().one()
        profile = conn.execute(select(profiles).where(
            profiles.c.code == 'PRO-A')).mappings().one()
    # 两个并发事务结束后，作废与释放必然同时可见，不存在中间态
    assert profile['voided'] is True
    assert order['state'] == '已暂停（曲线失效）'
    assert order['slot'] is None
