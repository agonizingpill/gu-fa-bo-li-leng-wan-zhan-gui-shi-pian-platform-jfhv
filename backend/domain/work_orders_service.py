from sqlalchemy import select

from core.records import get, insert, need, update
from domain.jigs_model import jigs
from domain.coupons_model import coupons
from domain.profiles_model import profiles
from domain.work_orders_model import work_orders


def book_jig(conn, user, data):
    profile = get(conn, profiles, data.profile)
    need(not profile['voided'], '依据曲线已失效，拒绝新委托')
    coupon = get(conn, coupons, profile['coupon'])
    jig = get(conn, jigs, data.jig, lock=True)
    need(jig['calibrated'], '该机位弯模尚未检定')
    need(max(profile['prediction'], coupon['target']) <= jig['max_throw'], '夹具有效行程不足，机位未占用')
    need(1 <= data.quantity <= 20, '本炉试片数超额')
    return insert(conn, work_orders, **data.model_dump(), state='待打样')


def complete(conn, user, data):
    order = get(conn, work_orders, data.order, lock=True)
    need(order['state'] == '待打样', '委托不在待打样状态，不能签回')
    need(data.witness.startswith('W-'), '见证号需使用 W- 前缀')
    return update(conn, work_orders, data.order, state='已打样 '+data.witness)


def basis(conn, order_code):
    """返回委托的完整原始依据，已打样与已暂停委托均可追溯。

    基准试片若已无法查清（来源不明的旧账），coupon 返回 null，
    曲线的失效状态仍保留在 profile 中可查。
    """
    order = get(conn, work_orders, order_code)
    profile = get(conn, profiles, order['profile'])
    coupon = conn.execute(select(coupons).where(
        coupons.c.code == profile['coupon'])).mappings().first()
    return {'order': order, 'profile': profile,
            'coupon': dict(coupon) if coupon is not None else None}
