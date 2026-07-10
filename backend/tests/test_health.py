from app.core.database import _mysql_server_url
from app.main import app
from fastapi.testclient import TestClient


def test_mysql_server_url_removes_database_name() -> None:
    url = _mysql_server_url("mysql+pymysql://root:123123@127.0.0.1:3306/pdm")

    assert url.database is None
    assert str(url).endswith(":3306")


def test_health_check() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
