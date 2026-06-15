import asyncio

from .base import AgentBase

class TestAgent(AgentBase):
    async def run(self, request):
        for i in range(5):
            yield f"data: TestAgent response for request '{request}' - step {i+1}/5\n\n"
            await asyncio.sleep(1)

    async def perform_action(self, action_name, *args, **kwargs):
        print(f"Performing action '{action_name}' with args {args} and kwargs {kwargs} on TestAgent with id {self.agent_id}")