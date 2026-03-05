import pytest


@pytest.mark.asyncio
async def test_register_and_login(client):
    reg = await client.post('/auth/register', json={'email': 'user1@example.com', 'password': 'password123'})
    assert reg.status_code == 200
    token = reg.json()['access_token']

    me = await client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200
    assert me.json()['email'] == 'user1@example.com'

    login = await client.post('/auth/login', json={'email': 'user1@example.com', 'password': 'password123'})
    assert login.status_code == 200
    assert login.json()['access_token']
