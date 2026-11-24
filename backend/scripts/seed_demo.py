import json
from sqlalchemy import func, select

from core.db import transaction
from domain.demo import FIXTURES

def seed():
    sizes = {}
    with transaction() as conn:
        for table, rows in FIXTURES:
            if 'code' in table.c:
                for row in rows:
                    present = conn.scalar(select(table.c.code).where(table.c.code == row['code']))
                    if present is None:
                        conn.execute(table.insert().values(**row))
            else:
                # 无业务主键的流水表（如 coupon_revisions）：仅在空表时播种，避免重复
                if conn.scalar(select(func.count()).select_from(table)) == 0:
                    for row in rows:
                        conn.execute(table.insert().values(**row))
            sizes[table.name] = conn.scalar(select(func.count()).select_from(table))
    return sizes

if __name__ == '__main__':
    print(json.dumps(seed(), ensure_ascii=False, sort_keys=True))
