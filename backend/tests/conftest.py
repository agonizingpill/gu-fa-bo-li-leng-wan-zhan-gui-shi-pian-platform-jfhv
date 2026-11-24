import os

os.environ.setdefault('DATABASE_URL', 'sqlite+pysqlite:///:memory:')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('JWT_SECRET', 'test-secret')
os.environ.setdefault('SEED_DEMO', 'false')

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import core.db as db
import core.queueing as queueing


@pytest.fixture()
def engine():
    # 确保全部表模型在 create_all 前注册到 metadata
    from domain import jigs_model, coupons_model, profiles_model, work_orders_model  # noqa: F401
    engine = create_engine(
        'sqlite+pysqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    db.engine = engine
    db.metadata.create_all(engine)
    yield engine
    db.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def broker():
    fake = fakeredis.FakeRedis(decode_responses=True)
    queueing.broker = fake
    return fake


@pytest.fixture()
def client(engine, broker):
    from core.app import app
    from core import auth

    def override(role):
        def _actor():
            return {'sub': f'{role}@demo.test', 'role': role}
        return _actor

    app.dependency_overrides[auth.actor] = override('reviewer')
    with TestClient(app) as c:
        c.override = override
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def as_role(client):
    from core.app import app
    from core import auth

    def switch(role):
        app.dependency_overrides[auth.actor] = client.override(role)
    return switch
