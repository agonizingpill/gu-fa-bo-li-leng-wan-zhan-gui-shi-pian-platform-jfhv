import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert

from core.db import transaction
from core.queueing import QUEUE
from domain.jigs_model import jigs
from domain.learning import calculate
from domain.profiles_model import profiles


def _drain_queue(broker):
    """模拟 worker：取出排队任务、执行拟合并回写结果。"""
    for _ in range(broker.llen(QUEUE)):
        item = broker.lmove(QUEUE, f'{QUEUE}:processing')
        job = json.loads(item)
        status = {'owner': job['owner'], 'input': job['input'],
                  'status': 'ready', 'result': calculate(job['input'])}
        broker.set(f'compute:{job["token"]}', json.dumps(status, allow_nan=False), ex=86400)
        broker.lrem(f'{QUEUE}:processing', 1, item)


@pytest.fixture()
def raw_client(engine, broker):
    from core.app import app
    with TestClient(app) as c:
        yield c


def _login(client, role):
    resp = client.post('/auth/login',
                       json={'email': f'{role}@demo.test', 'password': 'DemoC0de!2026'})
    assert resp.status_code == 200
    return {'Authorization': 'Bearer ' + resp.json()['token']}


def test_full_business_flow(raw_client, broker):
    operator = _login(raw_client, 'operator')
    reviewer = _login(raw_client, 'reviewer')
    viewer = _login(raw_client, 'viewer')

    # 夹具来自台账登记（演示环境由种子数据提供），这里直接入账
    with transaction() as conn:
        conn.execute(insert(jigs).values(
            code='CL-44', spread=180, max_throw=32, calibrated=True))

    # 作业员登记 13 张试片，复核员逐一见证
    for i in range(13):
        code = f'GP-{i:02d}'
        r = raw_client.post('/coupons/record-coupon', json={
            'code': code, 'jig': 'CL-44', 'heat': 410 + i * 9, 'thick': 2 + i % 4,
            'target': 10, 'measured': 5.0 + i * 0.3}, headers=operator)
        assert r.status_code == 200, r.text
        assert raw_client.post('/coupons/witness', json={'coupon': code},
                               headers=reviewer).status_code == 200

    # 作业员无权更正
    denied = raw_client.post('/coupons/correct-measured', json={
        'coupon': 'GP-12', 'measured': 9.6, 'reason': '抄错'}, headers=operator)
    assert denied.status_code == 403

    # 拟合 → 模拟 worker 计算 → 复核员签注
    fit = raw_client.post('/profiles/fit-curve',
                          json={'coupon': 'GP-12', 'penalty': 0.035}, headers=operator)
    assert fit.status_code == 200
    token = fit.json()['token']
    _drain_queue(broker)
    compute = raw_client.get(f'/compute/{token}', headers=operator).json()
    assert compute['status'] == 'ready'

    signed = raw_client.post('/profiles/sign-profile',
                             json={'code': 'PRO-1', 'token': token}, headers=reviewer)
    assert signed.status_code == 200, signed.text

    # 分配机位
    booked = raw_client.post('/work_orders/book-jig', json={
        'code': 'JOB-1', 'profile': 'PRO-1', 'jig': 'CL-44',
        'slot': '11-25 09:00', 'quantity': 2}, headers=operator)
    assert booked.status_code == 200, booked.text

    # 复核员更正读数：曲线作废 + 委托暂停释放机位，同一请求内完成
    corrected = raw_client.post('/coupons/correct-measured', json={
        'coupon': 'GP-12', 'measured': 9.6, 'reason': '见证后发现抄错'}, headers=reviewer)
    assert corrected.status_code == 200
    profile = next(p for p in raw_client.get('/profiles', headers=viewer).json()
                   if p['code'] == 'PRO-1')
    assert profile['voided'] is True
    order = next(o for o in raw_client.get('/work_orders', headers=viewer).json()
                 if o['code'] == 'JOB-1')
    assert order['state'] == '已暂停（曲线失效）'
    assert order['slot'] is None

    # 原时段已释放，可重新占用
    rebook = raw_client.post('/work_orders/book-jig', json={
        'code': 'JOB-2', 'profile': 'PRO-1', 'jig': 'CL-44',
        'slot': '11-25 09:00', 'quantity': 1}, headers=operator)
    assert rebook.status_code == 409  # PRO-1 已失效，拒绝新委托

    # 旧拟合任务即使完成，读数已更正也拒绝签注
    stale = raw_client.post('/profiles/sign-profile',
                            json={'code': 'PRO-STALE', 'token': token}, headers=reviewer)
    assert stale.status_code == 409

    # 无源曲线作废
    with transaction() as conn:
        conn.execute(insert(profiles).values(
            code='PRO-OLD', coupon='GP-MISSING', prediction=8.0, mae=1.0,
            curve={'terms': []}, token='tok-old', voided=False, void_reason=None))
    orphan = raw_client.post('/profiles/void-orphan',
                             json={'profile': 'PRO-OLD'}, headers=reviewer)
    assert orphan.status_code == 200
    assert orphan.json()['voided'] is True

    # 只读访客可查台账与更正流水
    revisions = raw_client.get('/coupons/GP-12/revisions', headers=viewer)
    assert revisions.status_code == 200
    assert revisions.json()[0]['measured_before'] == 8.6
