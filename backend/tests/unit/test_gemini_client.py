import pytest

from app.ai.gemini_client import (
    _classify,
    GeminiTransientError,
    GeminiConfigError,
)


@pytest.mark.unit
def test_classify_transient_rate_limit_with_retry_delay():
    raw_error = Exception(
        "ResourceExhausted: 429 Resource has been exhausted (e.g. check quota). "
        "Details: [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '35s'}]"
    )
    classified = _classify(raw_error)
    assert isinstance(classified, GeminiTransientError)
    assert classified.retry_after == 35
    assert "Gemini temporarily unavailable" in str(classified)


@pytest.mark.unit
def test_classify_transient_503_high_demand():
    raw_error = Exception(
        "503 Service Unavailable: The model is currently overloaded. Please try again later."
    )
    classified = _classify(raw_error)
    assert isinstance(classified, GeminiTransientError)
    assert classified.retry_after is None


@pytest.mark.unit
def test_classify_config_fault_retired_model():
    raw_error = Exception("404 models/gemini-1.5-flash was not found")
    classified = _classify(raw_error)
    assert isinstance(classified, GeminiConfigError)
    assert "Gemini configuration fault" in str(classified)


@pytest.mark.unit
def test_classify_config_fault_invalid_api_key():
    raw_error = Exception("API key not valid. Please pass a valid API key.")
    classified = _classify(raw_error)
    assert isinstance(classified, GeminiConfigError)


@pytest.mark.unit
def test_classify_non_gemini_error_passes_through():
    raw_error = ValueError("Local formatting error")
    classified = _classify(raw_error)
    assert classified is raw_error

