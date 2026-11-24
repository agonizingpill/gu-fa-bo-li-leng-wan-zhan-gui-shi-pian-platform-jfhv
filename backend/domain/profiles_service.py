from sqlalchemy import select

from core.queueing import submit, result
from core.records import get, insert, need, scan
from domain.coupons_model import coupons
from domain.profiles_model import profiles


def fit_curve(conn, user, data):
    coupon = get(conn, coupons, data.coupon)
    need(coupon['locked'], '试片尚未经过尺规见证')
    need(.001 <= data.penalty <= .3, '正则强度超出试制档范围')
    history = [item for item in scan(conn, coupons) if item['locked'] and item['code'] != data.coupon]
    need(len(history) >= 12, '已确认历史少于十二张')
    return submit(user, {'history': history, 'coupon': coupon, 'penalty': data.penalty})


def sign_profile(conn, user, data):
    run = result(user, data.token)
    target, metric = run['input']['coupon'], run['result']
    current = get(conn, coupons, target['code'])
    # 排队期间读数被更正：用旧读数算出的结果即使完成也拒绝签注
    need(current['measured'] == target['measured'],
         '拟合使用的冷却读数已被更正，旧计算结果拒绝签注，请重新发起拟合')
    need(metric['prediction'] > 0 and metric['mae'] < 5, '曲线超过台面验证误差预算')
    return insert(conn, profiles, code=data.code, coupon=target['code'], prediction=metric['prediction'],
                  mae=metric['mae'], curve={'terms': metric['terms'], 'held_out': metric['held_out']},
                  token=data.token, voided=False)


def void_orphan(conn, user, data):
    """查不清试片来源的旧曲线按失效处理：基准试片已不存在即作废。"""
    profile = get(conn, profiles, data.profile, lock=True)
    source = conn.execute(select(coupons.c.code).where(
        coupons.c.code == profile['coupon'])).scalar()
    need(source is None, '曲线基准试片仍可追溯，不属于无源曲线')
    need(not profile['voided'], '该曲线已失效')
    conn.execute(profiles.update().where(profiles.c.code == data.profile).values(
        voided=True, void_reason=f'基准试片 {profile["coupon"]} 来源无法查清'))
    return get(conn, profiles, data.profile)
