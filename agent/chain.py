"""AlphaWhale agent chain — connects finance tools to a ChatModel.

Implements the tool-calling loop: the LLM decides which tools to call,
we execute them, and feed the results back until the LLM has a final answer.
"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.tool import ToolCall
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from agent.tools import compare_assets, get_stock_price, get_technical_indicators

TOOLS = [get_stock_price, get_technical_indicators, compare_assets]
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are AlphaWhale, an AI financial analyst embedded in a live trading terminal. "
            "Use the available tools to answer questions about stock prices, technical indicators, "
            "and asset comparisons. Always provide clear, actionable insights based on the data. "
            "Never output raw JSON, dictionaries, or data structures.",
        ),
        ("placeholder", "{messages}"),
    ]
)


def create_model(temperature: float = 0.0) -> Runnable:
    """Create a ChatOpenAI model with tools bound.

    Args:
        temperature: Controls randomness. 0.0 = deterministic, 1.0 = creative.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=temperature)
    return llm.bind_tools(TOOLS)


def invoke_tools(tool_calls: list[ToolCall]) -> list[ToolMessage]:
    """Execute tool calls and return results as ToolMessages."""
    results = []
    for call in tool_calls:
        try:
            tool = TOOLS_BY_NAME[call["name"]]
            output = str(tool.invoke(call["args"]))
        except KeyError:
            output = f"Error: unknown tool '{call['name']}'"
        except Exception as exc:
            output = f"Error executing {call['name']}: {exc}"
        results.append(ToolMessage(content=output, tool_call_id=call["id"]))
    return results


def run(user_input: str, temperature: float = 0.0, max_iterations: int = 10) -> str:
    """Run the AlphaWhale agent on a user question.

    Args:
        user_input: The user's question about crypto markets.
        temperature: LLM temperature setting.
        max_iterations: Safety limit on tool-calling rounds.

    Returns:
        The agent's final text response.
    """
    model = create_model(temperature=temperature)
    messages = PROMPT.invoke({"messages": [HumanMessage(content=user_input)]})

    # Tool-calling loop: keep going until the LLM stops requesting tools
    for _iteration in range(max_iterations):
        response: AIMessage = model.invoke(messages.to_messages())

        # If no tool calls, the LLM has a final answer
        if not response.tool_calls:
            return str(response.content)

        # Execute the requested tools and add results to the conversation
        messages_list = messages.to_messages() + [response]
        tool_results = invoke_tools(response.tool_calls)
        messages_list.extend(tool_results)

        # Replace messages for next iteration (prompt + history + tool results)
        messages = PROMPT.invoke(
            {"messages": messages_list[1:]}  # skip system (prompt re-adds it)
        )

    return "Agent stopped: reached maximum iterations without a final answer."
