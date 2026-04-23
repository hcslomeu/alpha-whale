"""Tests for the Instructor extraction wrapper."""

from unittest.mock import MagicMock, patch

import instructor
import pytest
from pydantic import BaseModel, Field

from core.exceptions import ExtractionError
from core.extraction import (
    _get_client,
    create_instructor_client,
    extract,
)

# ---------------------------------------------------------------------------
# Test model
# ---------------------------------------------------------------------------


class SampleModel(BaseModel):
    """Simple model for testing extraction."""

    name: str = Field(description="A person's name")
    age: int = Field(description="Age in years", ge=0)


# ---------------------------------------------------------------------------
# TestCreateInstructorClient
# ---------------------------------------------------------------------------


class TestCreateInstructorClient:
    """Tests for the create_instructor_client factory."""

    @patch("core.extraction.OpenAI")
    @patch("core.extraction.instructor.from_openai")
    def test_returns_patched_client(self, mock_from_openai, mock_openai):
        """Creates and patches a default OpenAI client."""
        mock_patched = MagicMock()
        mock_from_openai.return_value = mock_patched

        result = create_instructor_client()

        mock_openai.assert_called_once()
        mock_from_openai.assert_called_once_with(
            mock_openai.return_value, mode=instructor.Mode.TOOLS
        )
        assert result is mock_patched

    @patch("core.extraction.instructor.from_openai")
    def test_accepts_custom_openai_client(self, mock_from_openai):
        """Uses a provided OpenAI client instead of creating one."""
        custom_client = MagicMock()
        create_instructor_client(openai_client=custom_client)

        mock_from_openai.assert_called_once_with(custom_client, mode=instructor.Mode.TOOLS)

    @patch("core.extraction.OpenAI")
    @patch("core.extraction.instructor.from_openai")
    def test_accepts_custom_mode(self, mock_from_openai, mock_openai):
        """Passes custom Instructor mode to from_openai."""
        create_instructor_client(mode=instructor.Mode.JSON)

        mock_from_openai.assert_called_once_with(
            mock_openai.return_value, mode=instructor.Mode.JSON
        )


# ---------------------------------------------------------------------------
# TestExtract
# ---------------------------------------------------------------------------


class TestExtract:
    """Tests for the extract convenience function."""

    @patch("core.extraction._get_client")
    def test_returns_validated_model(self, mock_get_client):
        """Returns a validated Pydantic model from the LLM response."""
        expected = SampleModel(name="Alice", age=30)
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = expected
        mock_get_client.return_value = mock_client

        result = extract("Alice is 30 years old", SampleModel)

        assert result == expected
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o-mini",
            response_model=SampleModel,
            max_retries=2,
            messages=[{"role": "user", "content": "Alice is 30 years old"}],
        )

    @patch("core.extraction._get_client")
    def test_raises_extraction_error_on_failure(self, mock_get_client):
        """Wraps LLM/validation errors in ExtractionError."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = ValueError("bad response")
        mock_get_client.return_value = mock_client

        with pytest.raises(ExtractionError, match="SampleModel"):
            extract("invalid input", SampleModel)

    @patch("core.extraction._get_client")
    def test_custom_model_parameter(self, mock_get_client):
        """Passes custom model name to the LLM call."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = SampleModel(name="Bob", age=25)
        mock_get_client.return_value = mock_client

        extract("Bob is 25", SampleModel, model="gpt-4o")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o"

    @patch("core.extraction._get_client")
    def test_custom_max_retries(self, mock_get_client):
        """Passes custom max_retries to the LLM call."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = SampleModel(name="Eve", age=28)
        mock_get_client.return_value = mock_client

        extract("Eve is 28", SampleModel, max_retries=5)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["max_retries"] == 5


# ---------------------------------------------------------------------------
# TestLazyInit
# ---------------------------------------------------------------------------


class TestLazyInit:
    """Tests for the lazy initialization pattern."""

    @patch("core.extraction._client", None)
    @patch("core.extraction.create_instructor_client")
    def test_creates_client_on_first_call(self, mock_create):
        """Lazily creates a client on first _get_client() call."""
        mock_create.return_value = MagicMock()
        _get_client()
        mock_create.assert_called_once()

    @patch("core.extraction._client", MagicMock())
    @patch("core.extraction.create_instructor_client")
    def test_reuses_cached_client(self, mock_create):
        """Returns cached client on subsequent calls."""
        _get_client()
        mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# TestExtractionErrorInheritance
# ---------------------------------------------------------------------------


class TestExtractionErrorInheritance:
    """Tests for ExtractionError exception hierarchy."""

    def test_inherits_from_pycor_error(self):
        """ExtractionError is a PyCorError subclass."""
        from core.exceptions import PyCorError

        err = ExtractionError("test error")
        assert isinstance(err, PyCorError)

    def test_stores_details(self):
        """ExtractionError preserves details dict."""
        err = ExtractionError("failed", details={"model": "gpt-4o"})
        assert err.details == {"model": "gpt-4o"}
        assert err.message == "failed"
