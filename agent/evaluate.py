"""Evaluation datasets and heuristic evaluators for AlphaWhale agent.

Provides:
- EVALUATION_EXAMPLES: curated test cases with expected tool trajectories
- Heuristic evaluator functions for use with LangSmith's evaluate()
- Runner functions to create datasets and execute evaluations
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langsmith import Client

if TYPE_CHECKING:
    from langsmith.schemas import Dataset, Example, Run

# ---------------------------------------------------------------------------
# Dataset: curated (input, expected_output) pairs
# ---------------------------------------------------------------------------

EVALUATION_EXAMPLES: list[dict[str, Any]] = [
    {
        "inputs": {"question": "What is the current Bitcoin price?"},
        "outputs": {
            "expected_tools": ["fetch_btc_price"],
            "min_response_length": 20,
        },
    },
    {
        "inputs": {
            "question": "Calculate the RSI for these prices: "
            "[100, 102, 101, 105, 107, 110, 108, 112, 115, 113, 116, 118, 120, 119, 121]"
        },
        "outputs": {
            "expected_tools": ["calculate_rsi"],
            "min_response_length": 20,
        },
    },
    {
        "inputs": {"question": "Give me an overview of the crypto market right now."},
        "outputs": {
            "expected_tools": ["get_market_summary"],
            "min_response_length": 30,
        },
    },
    {
        "inputs": {"question": "What is Bitcoin's price and the overall market conditions?"},
        "outputs": {
            "expected_tools": ["fetch_btc_price", "get_market_summary"],
            "min_response_length": 40,
        },
    },
]

# ---------------------------------------------------------------------------
# Heuristic evaluators (pure logic, no LLM calls)
# ---------------------------------------------------------------------------


def correct_tool_used(run: Run, example: Example) -> dict[str, Any]:
    """Check if the agent called the expected tool(s).

    Inspects the run's child runs for tool invocations and compares
    against the expected_tools listed in the dataset example.
    """
    expected = set(example.outputs.get("expected_tools", [])) if example.outputs else set()
    actual_tools: set[str] = set()

    if hasattr(run, "child_runs") and run.child_runs:
        for child in run.child_runs:
            if child.run_type == "tool":
                actual_tools.add(child.name)

    if not actual_tools and run.outputs:
        output_text = str(run.outputs.get("answer", "")).lower()
        for tool_name in expected:
            readable = tool_name.replace("_", " ")
            if readable in output_text or tool_name in output_text:
                actual_tools.add(tool_name)

    matches = expected & actual_tools
    score = len(matches) / len(expected) if expected else 1.0

    return {
        "key": "correct_tool_used",
        "score": score,
        "comment": f"Expected: {sorted(expected)}, Found: {sorted(actual_tools)}",
    }


def response_quality(run: Run, example: Example) -> dict[str, Any]:
    """Check if the response is non-empty and meets minimum length."""
    output_text = ""
    if run.outputs:
        output_text = str(run.outputs.get("answer", ""))

    min_length = 10
    if example.outputs:
        min_length = example.outputs.get("min_response_length", 10)

    is_non_empty = len(output_text.strip()) > 0
    meets_length = len(output_text) >= min_length
    score = 1.0 if (is_non_empty and meets_length) else 0.0

    return {
        "key": "response_quality",
        "score": score,
        "comment": f"Length: {len(output_text)}, Min: {min_length}",
    }


# ---------------------------------------------------------------------------
# Runner functions (require LangSmith API key)
# ---------------------------------------------------------------------------


def create_dataset(
    client: Client,
    dataset_name: str = "alpha-whale-eval",
    description: str = "AlphaWhale agent evaluation dataset",
) -> Dataset:
    """Create a new evaluation dataset in LangSmith."""
    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description=description,
    )

    for example in EVALUATION_EXAMPLES:
        client.create_example(
            inputs=example["inputs"],
            outputs=example["outputs"],
            dataset_id=dataset.id,
        )

    return dataset


def run_evaluation(client: Client, dataset_name: str = "alpha-whale-eval") -> Any:
    """Run evaluators against the dataset using the AlphaWhale agent."""
    from langsmith.evaluation import evaluate

    from agent.graph import run as agent_run

    def target(inputs: dict[str, Any]) -> dict[str, str]:
        answer = agent_run(inputs["question"])
        return {"answer": answer}

    return evaluate(
        target,
        data=dataset_name,
        evaluators=[correct_tool_used, response_quality],
        experiment_prefix="alpha-whale-eval",
        metadata={"agent_version": "0.1.0"},
        client=client,
    )
