import logging

import uvicorn

from .app import create_app
from .server.agent_selector import init_agents

init_agents()
app = create_app()

def main() -> None:
    # uvicorn only configures its own loggers; add a root handler so the
    # reference agents' logging (e.g. the assembled prompt in LLMAgent) shows.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
