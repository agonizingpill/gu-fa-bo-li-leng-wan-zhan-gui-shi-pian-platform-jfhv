import pytest


@pytest.fixture()
def world(client):
    """搭出一套完整链路：弯模、13 张锁定试片、失效/有效曲线、待打样/已打样委托。"""
    from sqlalchemy import insert
    from core.db import transaction
    from domain.jigs_model import jigs
    from domain.coupons_model import coupons
    from domain.profiles_model import profiles
    from domain.work_orders_model import work_orders

    with transaction() as conn:
        conn.execute(insert(jigs).values(code='CL-44', spread=180, max_throw=32, calibrated=True))
        conn.execute(insert(jigs).values(code='CL-18', spread=115, max_throw=8, calibrated=True))
        for i in range(13):
            conn.execute(insert(coupons).values(
                code=f'GP-{i:02d}', jig='CL-44', heat=410 + i * 9, thick=2 + i % 4,
                target=10, measured=5.0 + i * 0.3, locked=True))
        # GP-12 是后续要更正的对象；GP-99 作为无源曲线的悬空基准
        conn.execute(insert(profiles).values(
            code='PRO-A', coupon='GP-12', prediction=9.0, mae=1.2,
            curve={'terms': ['x0']}, token='tok-A', voided=False, void_reason=None))
        conn.execute(insert(profiles).values(
            code='PRO-B', coupon='GP-00', prediction=9.0, mae=1.2,
            curve={'terms': ['x0']}, token='tok-B', voided=False, void_reason=None))
        conn.execute(insert(profiles).values(
            code='PRO-ORPHAN', coupon='GP-99', prediction=8.0, mae=1.0,
            curve={'terms': ['x0']}, token='tok-ORPHAN', voided=False, void_reason=None))
        conn.execute(insert(work_orders).values(
            code='JOB-PENDING', profile='PRO-A', jig='CL-44',
            slot='11-25 09:00', quantity=2, state='待打样'))
        conn.execute(insert(work_orders).values(
            code='JOB-DONE', profile='PRO-A', jig='CL-44',
            slot='11-25 14:00', quantity=1, state='已打样 W-0302'))
        conn.execute(insert(work_orders).values(
            code='JOB-OTHER', profile='PRO-B', jig='CL-44',
            slot='11-26 09:00', quantity=3, state='待打样'))
    return client
