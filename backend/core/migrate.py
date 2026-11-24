"""演示库的最小幂等迁移：metadata.create_all 不会给已存在的表补列或改约束，
这里对既有表执行 ADD COLUMN / 放开 NOT NULL；全新库由 create_all 直接建出完整结构。"""
from sqlalchemy import inspect, text

from core.db import engine, metadata

COLUMN_PATCHES = {
    'coupons': [
        ('measured_original', 'FLOAT'),
        ('revision_note', 'VARCHAR(200)'),
        ('revised_at', 'TIMESTAMP'),
    ],
    'profiles': [
        ('voided', 'BOOLEAN NOT NULL DEFAULT FALSE'),
        ('void_reason', 'VARCHAR(200)'),
    ],
}


def _release_slot_not_null(conn, inspector):
    if 'work_orders' not in inspector.get_table_names():
        return
    slot = next((column for column in inspector.get_columns('work_orders')
                 if column['name'] == 'slot'), None)
    if slot is None or slot['nullable']:
        return
    if engine.dialect.name == 'postgresql':
        conn.execute(text('ALTER TABLE work_orders ALTER COLUMN slot DROP NOT NULL'))
    elif engine.dialect.name == 'sqlite':
        # SQLite 不支持 ALTER COLUMN，按官方做法重建表；无其他表外键引用 work_orders
        conn.execute(text('PRAGMA foreign_keys=OFF'))
        conn.execute(text('''CREATE TABLE work_orders_new (
            code VARCHAR(64) NOT NULL PRIMARY KEY,
            profile VARCHAR(160) NOT NULL REFERENCES profiles(code),
            jig VARCHAR(160) NOT NULL REFERENCES jigs(code),
            slot VARCHAR(160) UNIQUE,
            quantity INTEGER NOT NULL CHECK (quantity between 1 and 20),
            state VARCHAR(160) NOT NULL)'''))
        conn.execute(text('''INSERT INTO work_orders_new
            (code, profile, jig, slot, quantity, state)
            SELECT code, profile, jig, slot, quantity, state FROM work_orders'''))
        conn.execute(text('DROP TABLE work_orders'))
        conn.execute(text('ALTER TABLE work_orders_new RENAME TO work_orders'))
        conn.execute(text('PRAGMA foreign_keys=ON'))
    else:
        raise RuntimeError(f'未支持的迁移方言: {engine.dialect.name}')


def upgrade():
    # 先为既有库补齐新增表（全新库的全部表同样由此建出）
    from domain import jigs_model, coupons_model, profiles_model, work_orders_model  # noqa: F401
    metadata.create_all(engine, tables=[coupons_model.coupon_revisions])
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in COLUMN_PATCHES.items():
            if table not in existing:
                continue
            present = {column['name'] for column in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in present:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
        _release_slot_not_null(conn, inspector)
