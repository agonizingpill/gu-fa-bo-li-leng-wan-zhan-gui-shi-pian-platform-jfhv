from sqlalchemy import Boolean, CheckConstraint, Column, Float, ForeignKey, Integer, JSON, String, Table

from core.db import metadata


work_orders = Table('work_orders', metadata,
    Column('code', String(64), primary_key=True),
    Column('profile', String(160), ForeignKey('profiles.code'), nullable=False),
    Column('jig', String(160), ForeignKey('jigs.code'), nullable=False),
    # 委托暂停时机位时段释放（置空），同一时段可被新委托重新占用
    Column('slot', String(160), nullable=True, unique=True),
    Column('quantity', Integer, nullable=False),
    Column('state', String(160), nullable=False),
    CheckConstraint('quantity between 1 and 20'),
)
