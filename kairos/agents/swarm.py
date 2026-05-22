"""Kairos Swarm — LangGraph multi-agent system for specialized coaching conversations.

Uses `create_swarm()` from langgraph-swarm to route between specialist agents
(coach, financial, health, etc.) with automatic handoff based on context.
"""

import logging
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph_swarm import create_handoff_tool, create_swarm

logger = logging.getLogger(__name__)


def create_kairos_swarm(llm_model: str = "deepseek-chat", api_key: str = "", base_url: str = ""):
    from langchain.agents import create_agent

    llm_config = {"model": llm_model, "api_key": api_key}
    if base_url:
        llm_config["base_url"] = base_url

    coach = create_agent(
        f"openai:{llm_model}",
        tools=[
            create_handoff_tool(
                agent_name="financial_coach",
                description="Transfer to the financial coaching specialist when the client asks about money, budgeting, investments, or debt.",
            ),
            create_handoff_tool(
                agent_name="health_coach",
                description="Transfer to the health & wellness coaching specialist when the client asks about health, exercise, stress, or sleep.",
            ),
        ],
        system_prompt=(
            "You are a warm, empathetic KAIROS coaching assistant. "
            "You help clients with personal growth, emotional support, and life coaching. "
            "Keep responses concise, natural, and conversational. "
            "If the client asks about financial topics, transfer to the financial coach. "
            "If they ask about health/wellness topics, transfer to the health coach. "
            "Otherwise, handle the conversation yourself."
        ),
        name="Coach",
    )

    financial_coach = create_agent(
        f"openai:{llm_model}",
        tools=[
            create_handoff_tool(
                agent_name="Coach",
                description="Transfer back to the main coaching assistant when financial discussion is complete.",
            ),
        ],
        system_prompt=(
            "You are a KAIROS financial coaching specialist. "
            "You help clients with budgeting, saving, investing, debt management, and financial planning. "
            "Provide practical, actionable advice. "
            "When the financial topic is resolved, transfer back to the main coach."
        ),
        name="financial_coach",
    )

    health_coach = create_agent(
        f"openai:{llm_model}",
        tools=[
            create_handoff_tool(
                agent_name="Coach",
                description="Transfer back to the main coaching assistant when health discussion is complete.",
            ),
        ],
        system_prompt=(
            "You are a KAIROS health & wellness coaching specialist. "
            "You help clients with exercise routines, stress management, sleep hygiene, and healthy habits. "
            "Provide science-based, actionable advice. "
            "When the health topic is resolved, transfer back to the main coach."
        ),
        name="health_coach",
    )

    checkpointer = InMemorySaver()
    workflow = create_swarm(
        [coach, financial_coach, health_coach],
        default_active_agent="Coach",
    )
    return workflow.compile(checkpointer=checkpointer)


def run_swarm_turn(app, message: str, thread_id: str = "default") -> dict[str, Any]:
    config = {"configurable": {"thread_id": thread_id}}
    result = app.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config,
    )
    messages = result.get("messages", [])
    last = messages[-1] if messages else None
    return {
        "response": last.content if last and hasattr(last, "content") else "",
        "active_agent": result.get("active_agent", "Coach"),
        "messages": messages,
    }
