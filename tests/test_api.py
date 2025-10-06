def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_create_user(client):
    response = client.post(
        "/v1/users/",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass",
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["username"] == "testuser"
