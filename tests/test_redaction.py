from vllm_optimizer.reproduction.redaction import REDACTED, redact_arguments, redact_values


def test_redacts_nested_conventional_secret_names() -> None:
    document = {
        "API_KEY": "sentinel",
        "nested": [{"AWS_ACCESS_KEY_ID": "sentinel"}, {"cookie": "sentinel"}],
        "headers": {"Authorization": "Bearer sentinel", "X-Trace": "safe"},
        "ordinary": "safe",
    }

    redacted = redact_values(document)

    assert redacted["API_KEY"] == REDACTED
    assert redacted["nested"][0]["AWS_ACCESS_KEY_ID"] == REDACTED
    assert redacted["nested"][1]["cookie"] == REDACTED
    assert redacted["headers"]["Authorization"] == REDACTED
    assert redacted["headers"]["X-Trace"] == "safe"
    assert redacted["ordinary"] == "safe"


def test_redacts_command_options_and_authorization_headers() -> None:
    values = [
        "--api-key",
        "sentinel",
        "--client-secret=sentinel",
        "--header",
        "Authorization: Bearer sentinel",
        "--name",
        "safe",
    ]

    assert redact_arguments(values) == [
        "--api-key",
        REDACTED,
        f"--client-secret={REDACTED}",
        "--header",
        f"Authorization: {REDACTED}",
        "--name",
        "safe",
    ]
    assert redact_arguments(["--header=Authorization: Bearer sentinel"]) == [f"--header=Authorization: {REDACTED}"]
