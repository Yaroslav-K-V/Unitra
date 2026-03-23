"""Tests for standalone helpers in routes/generate.py and routes/runner.py."""
from routes.generate import _definitions_only, _count_tests


# ── _definitions_only ────────────────────────────────────────────────────────

def test_keeps_function_def():
    src = "def add(a, b):\n    return a + b"
    result = _definitions_only(src)
    assert "def add" in result


def test_keeps_class_def():
    src = "class Foo:\n    def bar(self): pass"
    result = _definitions_only(src)
    assert "class Foo" in result


def test_keeps_imports():
    src = "import os\nfrom pathlib import Path"
    result = _definitions_only(src)
    assert "import os" in result
    assert "from pathlib import Path" in result


def test_strips_module_level_assignment():
    src = "x = 42\ndef foo(): pass"
    result = _definitions_only(src)
    assert "x = 42" not in result
    assert "def foo" in result


def test_strips_module_level_call():
    src = "print('hello')\ndef foo(): pass"
    result = _definitions_only(src)
    assert "print" not in result
    assert "def foo" in result


def test_strips_class_instantiation():
    """Class instantiation at module level should be removed."""
    src = "class Dog:\n    def __init__(self, name): self.name = name\n\nrex = Dog('Rex')"
    result = _definitions_only(src)
    assert "rex = Dog" not in result
    assert "class Dog" in result


def test_empty_source():
    assert _definitions_only("") == ""


def test_invalid_syntax_returns_source():
    src = "def (broken:"
    assert _definitions_only(src) == src


# ── _count_tests ─────────────────────────────────────────────────────────────

def test_count_tests_none():
    assert _count_tests("import pytest\n") == 0


def test_count_tests_one():
    code = "import pytest\n\ndef test_foo():\n    pass"
    assert _count_tests(code) == 1


def test_count_tests_multiple():
    code = "\ndef test_a(): pass\n\ndef test_b(): pass\n\ndef test_c(): pass"
    assert _count_tests(code) == 3


def test_count_tests_does_not_count_helper():
    """A function not starting with test_ is not counted."""
    code = "\ndef test_foo(): pass\n\ndef helper(): pass"
    assert _count_tests(code) == 1
