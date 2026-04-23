"""Tests for exceptions module."""

from core.exceptions import ConfigurationError, PyCorError, ValidationError


class TestExceptions:
    """Tests for custom exceptions."""

    def test_pycor_error_stores_message(self) -> None:
        """PyCorError should store the message we pass in."""
        error = PyCorError("Something went wrong")

        assert error.message == "Something went wrong"
        assert str(error) == "Something went wrong"  # This works because of super().__init__

    def test_pycor_error_stores_details(self) -> None:
        """PyCorError should store optional details dict."""
        error = PyCorError("Error", details={"field": "email"})

        assert error.details == {"field": "email"}

    def test_pycor_error_defaults_to_empty_details(self) -> None:
        """When no details provided, should default to empty dict."""
        error = PyCorError("Error")

        assert error.details == {}

    def test_configuration_error_is_a_pycor_error(self) -> None:
        """ConfigurationError should be catchable as PyCorError."""
        error = ConfigurationError("Missing API key")

        assert isinstance(error, PyCorError)
        assert isinstance(error, Exception)

    def test_validation_error_is_a_pycor_error(self) -> None:
        """ValidationError should be catchable as PyCorError."""
        error = ValidationError("Invalid email format")

        assert isinstance(error, PyCorError)
