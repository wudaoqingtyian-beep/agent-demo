"""Demo project B: a deliberately failing test."""

import pytest


def test_expected_failure():
    assert 1 + 1 == 3  # This is intentionally wrong for demo
