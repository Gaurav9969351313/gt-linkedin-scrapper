from urllib.parse import parse_qs, urlparse

from conftest import PASSWORD, auth_headers, login, make_user


def invite_token(url: str) -> str:
    return parse_qs(urlparse(url).query)["token"][0]


def test_requires_auth(client):
    assert client.get("/api/candidates").status_code == 401
    assert client.get("/api/candidates", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_login_is_case_insensitive_and_rejects_bad_password(client):
    make_user("root@x.com", role="super_admin")
    assert login(client, "root@x.com", "wrong").status_code == 401
    res = login(client, "ROOT@x.com")
    assert res.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {res.json()['token']}"}).json()
    assert me["assignable_roles"] == ["user", "admin", "super_admin"]


def test_access_request_needs_approval(client, sent_emails):
    make_user("root@x.com", role="super_admin")
    body = {"name": "Req", "email": "req@x.com", "password": PASSWORD, "reason": "need it"}

    assert client.post("/api/auth/request-access", json={**body, "password": "short"}).status_code == 400
    assert client.post("/api/auth/request-access", json=body).status_code == 202
    assert sent_emails[-1][0] == ["root@x.com"]  # admins are notified
    assert client.post("/api/auth/request-access", json=body).status_code == 409

    res = login(client, "req@x.com")
    assert res.status_code == 403 and "waiting" in res.json()["detail"]

    root = auth_headers(client, "root@x.com")
    pending = client.get("/api/users?status=pending", headers=root).json()
    assert [u["email"] for u in pending] == ["req@x.com"]
    approved = client.post(f"/api/users/{pending[0]['id']}/approve", json={"role": "user"}, headers=root)
    assert approved.json()["status"] == "active"
    assert login(client, "req@x.com").status_code == 200


def test_rejected_user_can_request_again(client):
    make_user("root@x.com", role="super_admin")
    rej = make_user("rej@x.com", status="pending")
    root = auth_headers(client, "root@x.com")

    assert client.post(f"/api/users/{rej.id}/reject", headers=root).json()["status"] == "rejected"
    assert "not approved" in login(client, "rej@x.com").json()["detail"]
    body = {"name": "Rej", "email": "rej@x.com", "password": PASSWORD}
    assert client.post("/api/auth/request-access", json=body).status_code == 202


def test_invitation_flow(client):
    make_user("root@x.com", role="super_admin")
    root = auth_headers(client, "root@x.com")

    res = client.post("/api/invitations", json={"email": "adm@x.com", "role": "admin"}, headers=root)
    assert res.status_code == 201 and res.json()["email_sent"]
    token = invite_token(res.json()["invite_url"])
    assert client.get(f"/api/invitations/lookup?token={token}").json() == {"email": "adm@x.com", "role": "admin"}

    accept = {"token": token, "name": "Adm", "password": PASSWORD}
    assert client.post("/api/invitations/accept", json=accept).status_code == 200
    assert client.post("/api/invitations/accept", json=accept).status_code == 404  # single use
    assert client.get("/api/auth/me", headers=auth_headers(client, "adm@x.com")).json()["role"] == "admin"


def test_resend_invalidates_old_link_and_revoke(client):
    make_user("adm@x.com", role="admin")
    adm = auth_headers(client, "adm@x.com")

    res = client.post("/api/invitations", json={"email": "new@x.com"}, headers=adm)
    old_token = invite_token(res.json()["invite_url"])
    inv_id = res.json()["invitation"]["id"]
    assert client.post(f"/api/invitations/{inv_id}/resend", headers=adm).status_code == 200
    assert client.get(f"/api/invitations/lookup?token={old_token}").status_code == 404

    invitations = client.get("/api/invitations", headers=adm).json()
    assert len(invitations) == 1
    assert client.delete(f"/api/invitations/{invitations[0]['id']}", headers=adm).status_code == 204
    assert client.get("/api/invitations", headers=adm).json() == []


def test_admin_limits(client):
    root = make_user("root@x.com", role="super_admin")
    make_user("adm@x.com", role="admin")
    pending = make_user("p@x.com", status="pending")
    adm = auth_headers(client, "adm@x.com")

    assert client.post("/api/invitations", json={"email": "x@x.com", "role": "admin"}, headers=adm).status_code == 403
    assert client.post(f"/api/users/{pending.id}/approve", json={"role": "admin"}, headers=adm).status_code == 403
    assert client.post(f"/api/users/{root.id}/disable", headers=adm).status_code == 403
    assert client.post(f"/api/users/{root.id}/disable", headers=auth_headers(client, "root@x.com")).status_code == 400

    manage = {u["email"]: u["can_manage"] for u in client.get("/api/users", headers=adm).json()}
    assert manage == {"root@x.com": False, "adm@x.com": False, "p@x.com": True}


def test_regular_user_cannot_administer(client):
    make_user("u@x.com")
    assert client.get("/api/users", headers=auth_headers(client, "u@x.com")).status_code == 403


def test_disable_takes_effect_immediately(client):
    make_user("adm@x.com", role="admin")
    user = make_user("u@x.com")
    adm = auth_headers(client, "adm@x.com")
    session = auth_headers(client, "u@x.com")

    assert client.post(f"/api/users/{user.id}/disable", headers=adm).status_code == 200
    assert client.get("/api/candidates/mine", headers=session).status_code == 401
    assert login(client, "u@x.com").status_code == 403
    assert client.post(f"/api/users/{user.id}/enable", headers=adm).status_code == 200
    assert client.get("/api/candidates/mine", headers=session).status_code == 200


def test_role_change_requires_super_admin(client):
    make_user("root@x.com", role="super_admin")
    make_user("adm@x.com", role="admin")
    user = make_user("u@x.com")

    body = {"role": "admin"}
    assert client.patch(f"/api/users/{user.id}/role", json=body, headers=auth_headers(client, "adm@x.com")).status_code == 403
    res = client.patch(f"/api/users/{user.id}/role", json=body, headers=auth_headers(client, "root@x.com"))
    assert res.json()["role"] == "admin"


def test_login_throttle(client):
    make_user("root@x.com", role="super_admin")
    for _ in range(5):
        login(client, "root@x.com", "bad")
    assert login(client, "root@x.com").status_code == 429
