"""Tests for AlphaWhale evaluation dataset and heuristic evaluators.

All tests mock LangSmith Run/Example objects to avoid API calls.
"""

from unittest.mock import MagicMock, patch

from agent.evaluate import (
    EVALUATION_EXAMPLES,
    correct_tool_used,
    create_dataset,
    response_quality,
    run_evaluation,
)

# --- Dataset structure ---


class TestDatasetStructure:
    def test_all_examples_have_required_keys(self):
        for i, example in enumerate(EVALUATION_EXAMPLES):
            assert "inputs" in example, f"Example {i} missing 'inputs'"
            assert "outputs" in example, f"Example {i} missing 'outputs'"
            assert "question" in example["inputs"], f"Example {i} missing 'question'"

    def test_all_examples_have_expected_tools(self):
        for i, example in enumerate(EVALUATION_EXAMPLES):
            tools = example["outputs"].get("expected_tools")
            assert isinstance(tools, list), f"Example {i}: expected_tools must be a list"
            assert len(tools) > 0, f"Example {i}: expected_tools must not be empty"

    def test_all_examples_have_min_response_length(self):
        for i, example in enumerate(EVALUATION_EXAMPLES):
            min_len = example["outputs"].get("min_response_length")
            assert isinstance(min_len, int), f"Example {i}: min_response_length must be int"
            assert min_len > 0, f"Example {i}: min_response_length must be positive"

    def test_dataset_has_at_least_three_examples(self):
        assert len(EVALUATION_EXAMPLES) >= 3


# --- correct_tool_used evaluator ---


class TestCorrectToolUsed:
    def _make_run(self, outputs: dict | None = None, child_runs: list | None = None) -> MagicMock:
        run = MagicMock()
        run.outputs = outputs
        run.child_runs = child_runs
        return run

    def _make_example(self, outputs: dict) -> MagicMock:
        example = MagicMock()
        example.outputs = outputs
        return example

    def _make_child_run(self, name: str, run_type: str = "tool") -> MagicMock:
        child = MagicMock()
        child.name = name
        child.run_type = run_type
        return child

    def test_perfect_match_via_child_runs(self):
        run = self._make_run(
            child_runs=[self._make_child_run("fetch_btc_price")],
        )
        example = self._make_example({"expected_tools": ["fetch_btc_price"]})

        result = correct_tool_used(run, example)

        assert result["key"] == "correct_tool_used"
        assert result["score"] == 1.0

    def test_no_match_returns_zero(self):
        run = self._make_run(
            child_runs=[self._make_child_run("get_market_summary")],
        )
        example = self._make_example({"expected_tools": ["fetch_btc_price"]})

        result = correct_tool_used(run, example)

        assert result["score"] == 0.0

    def test_partial_match_returns_fraction(self):
        run = self._make_run(
            child_runs=[self._make_child_run("fetch_btc_price")],
        )
        example = self._make_example({"expected_tools": ["fetch_btc_price", "get_market_summary"]})

        result = correct_tool_used(run, example)

        assert result["score"] == 0.5

    def test_fallback_to_output_text(self):
        """When no child_runs exist, check output text for tool names."""
        run = self._make_run(
            outputs={"answer": "I used fetch_btc_price to get the data."},
            child_runs=None,
        )
        example = self._make_example({"expected_tools": ["fetch_btc_price"]})

        result = correct_tool_used(run, example)

        assert result["score"] == 1.0

    def test_empty_expected_tools_returns_perfect_score(self):
        run = self._make_run(child_runs=[])
        example = self._make_example({"expected_tools": []})

        result = correct_tool_used(run, example)

        assert result["score"] == 1.0


# --- response_quality evaluator ---


class TestResponseQuality:
    def _make_run(self, outputs: dict | None = None) -> MagicMock:
        run = MagicMock()
        run.outputs = outputs
        return run

    def _make_example(self, outputs: dict) -> MagicMock:
        example = MagicMock()
        example.outputs = outputs
        return example

    def test_good_response_passes(self):
        run = self._make_run({"answer": "Bitcoin is currently at $55,000 with bullish momentum."})
        example = self._make_example({"min_response_length": 20})

        result = response_quality(run, example)

        assert result["key"] == "response_quality"
        assert result["score"] == 1.0

    def test_empty_response_fails(self):
        run = self._make_run({"answer": ""})
        example = self._make_example({"min_response_length": 10})

        result = response_quality(run, example)

        assert result["score"] == 0.0

    def test_short_response_fails(self):
        run = self._make_run({"answer": "Hi"})
        example = self._make_example({"min_response_length": 20})

        result = response_quality(run, example)

        assert result["score"] == 0.0

    def test_none_outputs_fails(self):
        run = self._make_run(outputs=None)
        example = self._make_example({"min_response_length": 10})

        result = response_quality(run, example)

        assert result["score"] == 0.0

    def test_defaults_to_min_length_10(self):
        run = self._make_run({"answer": "Short but ok"})
        example = self._make_example({})

        result = response_quality(run, example)

        assert result["score"] == 1.0


# --- Runner functions (mocked LangSmith client) ---


class TestCreateDataset:
    def test_creates_dataset_with_examples(self):
        mock_client = MagicMock()
        mock_dataset = MagicMock()
        mock_dataset.id = "dataset-123"
        mock_client.create_dataset.return_value = mock_dataset

        result = create_dataset(mock_client, dataset_name="test-dataset")

        assert result == mock_dataset
        mock_client.create_dataset.assert_called_once_with(
            dataset_name="test-dataset",
            description="AlphaWhale agent evaluation dataset",
        )
        assert mock_client.create_example.call_count == len(EVALUATION_EXAMPLES)

    def test_each_example_passed_to_client(self):
        mock_client = MagicMock()
        mock_dataset = MagicMock()
        mock_dataset.id = "ds-456"
        mock_client.create_dataset.return_value = mock_dataset

        create_dataset(mock_client)

        for i, call in enumerate(mock_client.create_example.call_args_list):
            assert call.kwargs["inputs"] == EVALUATION_EXAMPLES[i]["inputs"]
            assert call.kwargs["outputs"] == EVALUATION_EXAMPLES[i]["outputs"]
            assert call.kwargs["dataset_id"] == "ds-456"


class TestRunEvaluation:
    @patch("langsmith.evaluation.evaluate")
    @patch("agent.graph.run")
    def test_calls_evaluate_with_correct_args(
        self, mock_agent_run: MagicMock, mock_evaluate: MagicMock
    ):
        mock_client = MagicMock()
        mock_evaluate.return_value = MagicMock()

        run_evaluation(mock_client, dataset_name="test-eval")

        mock_evaluate.assert_called_once()
        call_kwargs = mock_evaluate.call_args
        assert call_kwargs.kwargs["data"] == "test-eval"
        assert len(call_kwargs.kwargs["evaluators"]) == 2
        assert call_kwargs.kwargs["experiment_prefix"] == "alpha-whale-eval"
        assert call_kwargs.kwargs["client"] is mock_client
