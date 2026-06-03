"""
Example: a hand-written LangGraph StateGraph (no `create_agent` helper).

Input shape over HTTP:

    {"input": {"messages": [{"role": "user", "content": "..."}]}}

The platform's LangChain adapter handles any object exposing
`astream_events(version="v2")`, so a bare `StateGraph(...).compile()` is
served identically to `create_agent` output.
"""

from __future__ import annotations

import os

from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode


@tool
def echo(text: str) -> str:
    """Echo the given text back unchanged."""
    return text


def _llm():
    return ChatOpenAI(
        model=os.environ.get("LANGGRAPH_HELLO_MODEL", "gpt-4o-mini"),
        temperature=0,
        streaming=True,
    ).bind_tools([echo])


def _route(state: MessagesState) -> str:
    """If the model called a tool, run it; else stop."""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def _model_node(state: MessagesState) -> dict:
    response = _llm().invoke(state["messages"])
    return {"messages": [response]}


def build_agent():
    """Factory: returns a compiled LangGraph state graph."""
    graph = StateGraph(MessagesState)
    graph.add_node("model", _model_node)
    graph.add_node("tools", ToolNode([echo]))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", _route, {"tools": "tools", END: END})
    graph.add_edge("tools", "model")
    return graph.compile()
