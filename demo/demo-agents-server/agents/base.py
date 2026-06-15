class AgentBase:
    def __init__(self, agent_id):
        self.agent_id = agent_id

    async def run(self, *args, **kwargs):
        raise NotImplementedError("This method should be implemented by subclasses")

    async def perform_action(self, action_name, *args, **kwargs):
        raise NotImplementedError("This method should be implemented by subclasses")