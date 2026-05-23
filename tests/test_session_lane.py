import asyncio

from app.agent.session_lane import SessionLaneManager


def test_session_lane_serializes_same_session_and_allows_other_sessions():
    lane = SessionLaneManager()
    events = []

    async def same_session(name):
        async with lane.lane(1, "s1"):
            events.append(f"{name}:start")
            await asyncio.sleep(0.01)
            events.append(f"{name}:end")

    async def other_session():
        async with lane.lane(2, "s1"):
            events.append("other:start")
            await asyncio.sleep(0)
            events.append("other:end")

    async def run():
        await asyncio.gather(same_session("a"), same_session("b"), other_session())

    asyncio.run(run())

    assert events.index("a:end") < events.index("b:start")
    assert "other:start" in events
