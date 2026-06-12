import pytest

from authsome.auth.models.enums import FlowType
from authsome.auth.sessions import AuthSessionStatus, AuthSessionStore, MemoryAuthSessionStore


@pytest.mark.asyncio
async def test_memory_session_store_create_get_save_and_delete() -> None:
    store = MemoryAuthSessionStore()
    session = await store.create(
        provider="github",
        identity="agent-1",
        principal_id="principal_1",
        connection_name="default",
        flow_type=FlowType.PKCE.value,
    )

    loaded = await store.get(session.session_id)
    loaded.state = AuthSessionStatus.WAITING_FOR_USER
    await store.save(loaded)

    assert (await store.get(session.session_id)).state == AuthSessionStatus.WAITING_FOR_USER

    await store.delete(session.session_id)
    with pytest.raises(KeyError):
        await store.get(session.session_id)


@pytest.mark.asyncio
async def test_memory_session_store_indexes_oauth_state() -> None:
    store = MemoryAuthSessionStore()
    session = await store.create(
        provider="github",
        identity="agent-1",
        principal_id="principal_1",
        connection_name="default",
        flow_type=FlowType.PKCE.value,
    )
    session.payload["internal_state"] = "state-123"

    await store.index_oauth_state(session)

    assert (await store.get_by_oauth_state("state-123")).session_id == session.session_id


def test_auth_session_store_alias_constructs_memory_store() -> None:
    assert isinstance(AuthSessionStore(), MemoryAuthSessionStore)
