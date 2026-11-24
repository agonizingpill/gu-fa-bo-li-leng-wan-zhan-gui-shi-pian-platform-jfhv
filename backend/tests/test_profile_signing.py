import json

from tests.fixtures import world  # noqa: F401


def _seed_compute(broker, token, measured):
    broker.set(f'compute:{token}', json.dumps({
        'owner': 'reviewer@demo.test',
        'status': 'ready',
        'input': {
            'coupon': {'code': 'GP-12', 'jig': 'CL-44', 'heat': 518, 'thick': 2,
                       'target': 10, 'measured': measured, 'locked': True,
                       'measured_original': None, 'revision_note': None, 'revised_at': None},
            'history': [],
            'penalty': 0.035,
        },
        'result': {'prediction': 9.5, 'mae': 1.1, 'held_out': 4, 'terms': ['x0']},
    }), ex=86400)


def test_sign_rejected_when_reading_corrected_after_fit(world, broker):
    _seed_compute(broker, 'tok-stale', measured=8.6)
    # 排队/待签注期间读数被更正
    world.post('/coupons/correct-measured',
               json={'coupon': 'GP-12', 'measured': 9.6, 'reason': '抄错复核'})
    resp = world.post('/profiles/sign-profile',
                      json={'code': 'PRO-NEW', 'token': 'tok-stale'})
    assert resp.status_code == 409
    assert '更正' in resp.json()['detail']
    # 没有产生新曲线
    assert all(p['code'] != 'PRO-NEW' for p in world.get('/profiles').json())


def test_sign_accepted_with_fresh_snapshot(world, broker):
    _seed_compute(broker, 'tok-fresh', measured=8.6)
    resp = world.post('/profiles/sign-profile',
                      json={'code': 'PRO-FRESH', 'token': 'tok-fresh'})
    assert resp.status_code == 200, resp.text
    profile = next(p for p in world.get('/profiles').json() if p['code'] == 'PRO-FRESH')
    assert profile['voided'] is False
