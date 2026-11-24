from fastapi import APIRouter, Depends

from core.auth import actor, allow
from core.audit import record
from core.db import transaction
from core.records import scan
from domain import coupons_service as service
from domain.coupons_model import coupons
from domain.coupons_schemas import CorrectCoupon, RecordCoupon, Witness

router = APIRouter()

@router.get('/coupons')
def list_coupons(user=Depends(actor)):
    with transaction() as conn:
        return scan(conn, coupons)


@router.get('/coupons/{code}/revisions')
def coupon_revisions(code: str, user=Depends(actor)):
    with transaction() as conn:
        return service.revisions(conn, code)


@router.post('/coupons/record-coupon')
def record_coupon(data: RecordCoupon, user=Depends(actor)):
    allow(user, ('operator', 'reviewer'))
    with transaction() as conn:
        output = service.record_coupon(conn, user, data)
        record(conn, user, 'coupons.record_coupon')
        return output


@router.post('/coupons/witness')
def witness(data: Witness, user=Depends(actor)):
    allow(user, ('reviewer',))
    with transaction() as conn:
        output = service.witness(conn, user, data)
        record(conn, user, 'coupons.witness')
        return output


@router.post('/coupons/correct-measured')
def correct_measured(data: CorrectCoupon, user=Depends(actor)):
    allow(user, ('reviewer',))
    with transaction() as conn:
        output = service.correct_coupon(conn, user, data)
        record(conn, user, 'coupons.correct_measured')
        return output
