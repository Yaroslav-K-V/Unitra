from agent import run_agent, stream_agent


class AgentAiRunner:
    def run(self, source_code: str) -> str:
        return run_agent(source_code)

    def stream(self, source_code: str):
        return stream_agent(source_code)
