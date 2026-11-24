from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Table

from core.db import metadata


coupons = Table('coupons', metadata,
    Column('code', String(64), primary_key=True),
    Column('jig', String(160), ForeignKey('jigs.code'), nullable=False),
    Column('heat', Float, nullable=False),
    Column('thick', Float, nullable=False),
    Column('target', Float, nullable=False),
    Column('measured', Float, nullable=False),
    # 更正留痕：measured_original 记录首次被更正前的原始读数，只写一次
    Column('measured_original', Float, nullable=True),
    Column('revision_note', String(200), nullable=True),
    Column('revised_at', DateTime, nullable=True),
    Column('locked', Boolean, nullable=False),
    CheckConstraint('thick > 0'),
    CheckConstraint('measured >= 0'),
    CheckConstraint('target > 0'),
)

# 每次读数更正的不可变流水，原读数始终可追溯
coupon_revisions = Table('coupon_revisions', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('coupon', String(160), ForeignKey('coupons.code'), nullable=False),
    Column('measured_before', Float, nullable=False),
    Column('measured_after', Float, nullable=False),
    Column('reason', String(200), nullable=False),
    Column('actor', String(160), nullable=False),
    Column('at', DateTime, nullable=False),
)
