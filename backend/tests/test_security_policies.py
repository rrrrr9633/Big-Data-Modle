from app.security.auth import CurrentUser
from app.security.policies import has_permission


def test_admin_has_all_permissions() -> None:
    user = CurrentUser(username="admin", role="admin")

    assert has_permission(user, "model.activate")
    assert has_permission(user, "ops.read")


def test_engineer_permissions_are_limited() -> None:
    user = CurrentUser(username="engineer", role="engineer")

    assert has_permission(user, "model.train")
    assert has_permission(user, "device.change.submit")
    assert not has_permission(user, "model.activate")
    assert not has_permission(user, "audit.read")


def test_unknown_role_has_no_permissions() -> None:
    assert not has_permission(CurrentUser(username="unknown", role="unknown"), "device.read")
