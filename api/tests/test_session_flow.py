import pytest


@pytest.mark.asyncio
async def test_session_source_quiz_flow(client):
    reg = await client.post('/auth/register', json={'email': 'user2@example.com', 'password': 'password123'})
    token = reg.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    created = await client.post('/sessions', json={'title': 'Session A', 'description': 'Desc'}, headers=headers)
    assert created.status_code == 200
    session_id = created.json()['id']

    add_source = await client.post(
        f'/sessions/{session_id}/sources',
        json={'source_type': 'url', 'url': 'https://example.com'},
        headers=headers,
    )
    assert add_source.status_code == 200

    quiz = await client.post(f'/quiz/sessions/{session_id}/generate', json={'mode': 'mcq'}, headers=headers)
    assert quiz.status_code == 200

    quiz_id = quiz.json()['id']
    submit = await client.post(f'/quiz/{quiz_id}/submit', json={'answers': [0, 0, 0, 0, 0]}, headers=headers)
    assert submit.status_code == 200
    assert 'score' in submit.json()
