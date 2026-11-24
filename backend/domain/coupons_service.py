from datetime import datetime, timezone

from sqlalchemy import select, update as sa_update

from core.records import get, insert, need, update as record_update
from domain.jigs_model import jigs
from domain.coupons_model import coupons, coupon_revisions
from domain.profiles_model import profiles
from domain.work_orders_model import work_orders


def record_coupon(conn, user, data):
    jig = get(conn, jigs, data.jig)
    need(jig['calibrated'], '弯模量具尚未确认')
    need(350 <= data.heat <= 650 and 1.5 <= data.thick <= 10, '超出试制保温或片厚范围')
    need(0 <= data.measured <= jig['max_throw'] and 0 < data.target <= jig['max_throw'], '试片超过弯模行程')
    return insert(conn, coupons, **data.model_dump(), locked=False)


def witness(conn, user, data):
    get(conn, coupons, data.coupon, lock=True)
    return record_update(conn, coupons, data.coupon, locked=True)


def correct_coupon(conn, user, data):
    """复核员更正冷却弯度。

    同一事务内依次完成：试片行锁定并留痕、受影响曲线作废、待打样委托暂停
    并释放机位时段。任一步失败整体回滚，保证曲线作废与机位释放同时生效。
    """
    coupon = get(conn, coupons, data.coupon, lock=True)
    need(coupon['locked'], '试片尚未经过尺规见证，不能走更正流程')
    need(0 <= data.measured, '冷却弯度不能为负')
    jig = get(conn, jigs, coupon['jig'])
    need(data.measured <= jig['max_throw'], '更正读数超过弯模行程')
    need(abs(coupon['measured'] - data.measured) > 1e-9, '更正读数与原读数相同')

    now = datetime.now(timezone.utc)
    measured_before = coupon['measured']
    measured_original = coupon['measured_original']
    if measured_original is None:
        measured_original = measured_before

    # 1. 保留原读数：首次更正固化原读数，后续更正不动原始值；并追加不可变流水
    conn.execute(coupon_revisions.insert().values(
        coupon=data.coupon, measured_before=measured_before, measured_after=data.measured,
        reason=data.reason, actor=user['sub'], at=now))
    conn.execute(sa_update(coupons).where(coupons.c.code == data.coupon).values(
        measured=data.measured, measured_original=measured_original,
        revision_note=data.reason, revised_at=now))

    # 2. 以该试片为基准的曲线全部作废（行已随试片锁串行化）
    affected = conn.execute(select(profiles.c.code).where(
        profiles.c.coupon == data.coupon, profiles.c.voided.is_(False))).scalars().all()
    if affected:
        conn.execute(sa_update(profiles).where(profiles.c.code.in_(affected)).values(
            voided=True, void_reason=f'基准试片 {data.coupon} 冷却弯度已更正'))

        # 3. 待打样委托暂停并释放机位；已打样委托保留状态与原依据
        conn.execute(sa_update(work_orders).where(
            work_orders.c.profile.in_(affected), work_orders.c.state == '待打样').values(
            state='已暂停（曲线失效）', slot=None))

    return get(conn, coupons, data.coupon)


def revisions(conn, coupon):
    rows = conn.execute(select(coupon_revisions).where(
        coupon_revisions.c.coupon == coupon).order_by(coupon_revisions.c.id)).mappings().all()
    return [dict(row) for row in rows]
