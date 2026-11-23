from collections.abc import Generator
from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parents[1]))
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.models import Household, Role, User


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    home = Household(name="Hogar de prueba")
    other_home = Household(name="Otro hogar")
    session.add_all([home, other_home]); session.flush()
    session.add_all([
        User(email="admin@test.local", password_hash=hash_password("secret"), role=Role.admin, household_id=home.id),
        User(email="member@test.local", password_hash=hash_password("secret"), role=Role.member, household_id=home.id),
        User(email="other@test.local", password_hash=hash_password("secret"), role=Role.member, household_id=other_home.id),
    ])
    session.commit()
    yield session
    session.close(); Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db) -> Generator[TestClient, None, None]:
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def token(client, email="admin@test.local"):
    response = client.post("/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
