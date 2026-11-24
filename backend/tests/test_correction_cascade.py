from tests.fixtures import world  # noqa: F401


def test_correction_keeps_original_reading(world):
    resp = world.post('/coupons/correct-measured',
                      json={'coupon': 'GP-12', 'measured': 9.6, 'reason': '抄错复核'})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body['measured'] == 9.6
    # 原读数保留在专门字段
    assert body['measured_original'] == 5.0 + 12 * 0.3
    assert body['revision_note'] == '抄错复核'

    revisions = world.get('/coupons/GP-12/revisions').json()
    assert len(revisions) == 1
    assert revisions[0]['measured_before'] == 8.6
    assert revisions[0]['measured_after'] == 9.6
    assert revisions[0]['reason'] == '抄错复核'


def test_correction_preserves_first_original_across_repeats(world):
    first = 5.0 + 12 * 0.3
    world.post('/coupons/correct-measured',
               json={'coupon': 'GP-12', 'measured': 9.6, 'reason': '第一次更正'})
    world.post('/coupons/correct-measured',
               json={'coupon': 'GP-12', 'measured': 9.9, 'reason': '第二次更正'})
    coupon = next(c for c in world.get('/coupons').json() if c['code'] == 'GP-12')
    assert coupon['measured'] == 9.9
    # 原始读数不被后续更正覆盖
    assert coupon['measured_original'] == first
    revisions = world.get('/coupons/GP-12/revisions').json()
    assert [r['measured_after'] for r in revisions] == [9.6, 9.9]


def test_correction_voids_profiles_and_releases_slots_together(world):
    resp = world.post('/coupons/correct-measured',
                      json={'coupon': 'GP-12', 'measured': 9.6, 'reason': '抄错复核'})
    assert resp.status_code == 200

    profiles = {p['code']: p for p in world.get('/profiles').json()}
    assert profiles['PRO-A']['voided'] is True
    assert '更正' in profiles['PRO-A']['void_reason']
    # 未引用该试片的曲线不受牵连
    assert profiles['PRO-B']['voided'] is False

    orders = {o['code']: o for o in world.get('/work_orders').json()}
    pending = orders['JOB-PENDING']
    assert pending['state'] == '已暂停（曲线失效）'
    # 机位时段在同一事务内释放
    assert pending['slot'] is None
    # 已打样委托保持原样，原依据不丢
    done = orders['JOB-DONE']
    assert done['state'] == '已打样 W-0302'
    assert done['slot'] == '11-25 14:00'
    # 其他曲线的待打样委托不受影响
    assert orders['JOB-OTHER']['state'] == '待打样'


def test_released_slot_can_be_rebooked(world):
    world.post('/coupons/correct-measured',
               json={'coupon': 'GP-12', 'measured': 9.6, 'reason': '抄错复核'})
    # 原时段已释放，可用有效曲线重新登记
    resp = world.post('/work_orders/book-jig', json={
        'code': 'JOB-NEW', 'profile': 'PRO-B', 'jig': 'CL-44',
        'slot': '11-25 09:00', 'quantity': 2})
    assert resp.status_code == 200, resp.text


def test_completed_order_still_exposes_original_basis(world):
    world.post('/coupons/correct-measured',
               json={'coupon': 'GP-12', 'measured': 9.6, 'reason': '抄错复核'})
    basis = world.get('/work_orders/JOB-DONE/basis').json()
    assert basis['order']['code'] == 'JOB-DONE'
    assert basis['profile']['code'] == 'PRO-A'
    assert basis['profile']['voided'] is True
    # 依据里的试片是更正后的记录，原始读数仍可从试片与更正流水追溯
    assert basis['coupon']['code'] == 'GP-12'
    assert basis['coupon']['measured_original'] == 8.6


def test_voided_profile_rejects_new_booking(world):
    world.post('/coupons/correct-measured',
               json={'coupon': 'GP-12', 'measured': 9.6, 'reason': '抄错复核'})
    resp = world.post('/work_orders/book-jig', json={
        'code': 'JOB-X', 'profile': 'PRO-A', 'jig': 'CL-44',
        'slot': '11-27 09:00', 'quantity': 1})
    assert resp.status_code == 409
    assert '失效' in resp.json()['detail']
    # 被拒绝时不占用机位
    assert all(o['code'] != 'JOB-X' for o in world.get('/work_orders').json())


def test_paused_order_cannot_be_completed(world):
    world.post('/coupons/correct-measured',
               json={'coupon': 'GP-12', 'measured': 9.6, 'reason': '抄错复核'})
    resp = world.post('/work_orders/complete',
                      json={'order': 'JOB-PENDING', 'witness': 'W-0999'})
    assert resp.status_code == 409


def test_correction_requires_reviewer(world, as_role):
    as_role('operator')
    resp = world.post('/coupons/correct-measured',
                      json={'coupon': 'GP-12', 'measured': 9.6, 'reason': '抄错复核'})
    assert resp.status_code == 403


def test_correction_same_value_and_unlocked_rejected(world, as_role):
    resp = world.post('/coupons/correct-measured',
                      json={'coupon': 'GP-12', 'measured': 8.6, 'reason': '无变化'})
    assert resp.status_code == 409

    # 未见证试片不能走更正
    world.post('/coupons/record-coupon', json={
        'code': 'GP-FRESH', 'jig': 'CL-44', 'heat': 500, 'thick': 3,
        'target': 10, 'measured': 7.0})
    as_role('reviewer')
    resp = world.post('/coupons/correct-measured',
                      json={'coupon': 'GP-FRESH', 'measured': 7.5, 'reason': '未见证'})
    assert resp.status_code == 409


def test_void_orphan_profile(world):
    resp = world.post('/profiles/void-orphan', json={'profile': 'PRO-ORPHAN'})
    assert resp.status_code == 200
    assert resp.json()['voided'] is True
    assert '来源' in resp.json()['void_reason']

    # 来源仍可追溯的曲线不能走无源作废
    resp = world.post('/profiles/void-orphan', json={'profile': 'PRO-B'})
    assert resp.status_code == 409

    # 作废后的曲线同样拒绝新委托
    resp = world.post('/work_orders/book-jig', json={
        'code': 'JOB-Y', 'profile': 'PRO-ORPHAN', 'jig': 'CL-44',
        'slot': '11-28 09:00', 'quantity': 1})
    assert resp.status_code == 409


def test_basis_survives_missing_source_coupon(world):
    from sqlalchemy import insert
    from core.db import transaction
    from domain.work_orders_model import work_orders
    with transaction() as conn:
        conn.execute(insert(work_orders).values(
            code='JOB-ORPHAN', profile='PRO-ORPHAN', jig='CL-44',
            slot='11-29 09:00', quantity=1, state='已打样 W-0777'))
    basis = world.get('/work_orders/JOB-ORPHAN/basis').json()
    assert basis['order']['code'] == 'JOB-ORPHAN'
    assert basis['profile']['code'] == 'PRO-ORPHAN'
    # 基准试片查不清时依据接口仍可用，coupon 显式为空
    assert basis['coupon'] is None
