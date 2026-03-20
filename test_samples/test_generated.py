import importlib.util
from pathlib import Path

import pytest


def load_module(module_name: str, file_name: str):
    path = Path(__file__).parent / file_name
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


one = load_module("one_module", "1.py")
two = load_module("two_module", "2.py")
calc = load_module("calculator_module", "3_calculator.py")
strings = load_module("string_utils_module", "4_string_utils.py")
user_mod = load_module("user_module", "5_user.py")


def test_hello_world_prints_expected_output(capsys):
    result = one.hello_world()
    captured = capsys.readouterr()
    assert result is None
    assert captured.out == "Hello, World!\n"


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (0, 0, 0),
        (1, 2, 3),
        (-1, 5, 4),
        (10**12, 10**12, 2 * 10**12),
    ],
)
def test_1py_add_various_inputs(a, b, expected):
    assert one.add(a, b) == expected


def test_1py_add_defaults():
    assert one.add() == 0


@pytest.mark.parametrize(
    "goal,status,expected",
    [
        (None, "achieved", "Please provide both goal and status."),
        ("Run a marathon", None, "Please provide both goal and status."),
        ("None", "achieved", "Please provide both goal and status."),
        ("Learn Python", "achieved", "Congratulations on achieving your goal: Learn Python!"),
        ("Learn Python", "in progress", "Keep going! You're making progress towards your goal: Learn Python."),
        ("Learn Python", "not started", "Don't wait! Start working on your goal: Learn Python today."),
    ],
)
def test_achieve_goal_cases(goal, status, expected):
    assert two.achieve_goal(goal=goal, status=status) == expected


def test_achieve_goal_unknown_status_returns_none():
    assert two.achieve_goal(goal="Learn Python", status="paused") is None


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (0, 0, 0),
        (2, 3, 5),
        (-2, 5, 3),
        (1.5, 2.25, 3.75),
        (10**18, 10**18, 2 * 10**18),
    ],
)
def test_calculator_add(a, b, expected):
    assert calc.add(a, b) == expected


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (0, 0, 0),
        (5, 3, 2),
        (-2, -3, 1),
        (1.5, 0.5, 1.0),
        (-10**18, 10**18, -2 * 10**18),
    ],
)
def test_calculator_subtract(a, b, expected):
    assert calc.subtract(a, b) == expected


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (0, 5, 0),
        (2, 3, 6),
        (-2, 3, -6),
        (-2, -3, 6),
        (1.5, 2, 3.0),
        (10**6, 10**6, 10**12),
    ],
)
def test_calculator_multiply(a, b, expected):
    assert calc.multiply(a, b) == expected


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (10, 2, 5),
        (9, 3, 3),
        (7.5, 2.5, 3.0),
        (-9, 3, -3),
        (0, 5, 0),
    ],
)
def test_calculator_divide(a, b, expected):
    assert calc.divide(a, b) == expected


@pytest.mark.parametrize("b", [0, 0.0])
def test_calculator_divide_by_zero_raises(b):
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        calc.divide(10, b)


@pytest.mark.parametrize(
    "base,exp,expected",
    [
        (0, 2, 0),
        (2, 2, 4),
        (2, 3, 8),
        (5, 0, 1),
        (2, -1, 0.5),
        (10**6, 2, 10**12),
    ],
)
def test_calculator_power(base, exp, expected):
    assert calc.power(base, exp) == expected


def test_calculator_power_default_exponent():
    assert calc.power(4) == 16


@pytest.mark.parametrize(
    "s,expected",
    [
        ("", ""),
        ("a", "a"),
        ("hello", "olleh"),
        ("racecar", "racecar"),
        ("12345", "54321"),
    ],
)
def test_reverse_string(s, expected):
    assert strings.reverse_string(s) == expected


@pytest.mark.parametrize(
    "s,expected",
    [
        ("", True),
        ("a", True),
        ("Racecar", True),
        ("A man a plan a canal Panama", True),
        ("hello", False),
        ("Was it a car or a cat I saw", True),
    ],
)
def test_is_palindrome(s, expected):
    assert strings.is_palindrome(s) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", 0),
        ("one", 1),
        ("two words", 2),
        (" multiple   spaces here ", 3),
        ("a b c d e", 5),
    ],
)
def test_count_words(text, expected):
    assert strings.count_words(text) == expected


@pytest.mark.parametrize(
    "text,max_length,suffix,expected",
    [
        ("short", 10, "...", "short"),
        ("exactlyten", 10, "...", "exactlyten"),
        ("hello world", 5, "...", "hello..."),
        ("abcdef", 3, "", "abc"),
        ("", 0, "...", ""),
    ],
)
def test_truncate(text, max_length, suffix, expected):
    assert strings.truncate(text, max_length=max_length, suffix=suffix) == expected


def test_truncate_with_large_max_length_returns_original():
    text = "x" * 1000
    assert strings.truncate(text, max_length=10**6) == text


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", ""),
        ("hello world", "Hello World"),
        ("multiple   spaces", "Multiple Spaces"),
        ("PYTHON", "Python"),
        ("a b c", "A B C"),
    ],
)
def test_capitalize_words(text, expected):
    assert strings.capitalize_words(text) == expected


def test_user_init_and_to_dict():
    user = user_mod.User("Alice", 30, "alice@example.com")
    assert user.name == "Alice"
    assert user.age == 30
    assert user.email == "alice@example.com"
    assert user.to_dict() == {"name": "Alice", "age": 30, "email": "alice@example.com"}


@pytest.mark.parametrize(
    "age,expected",
    [
        (0, False),
        (-1, False),
        (17, False),
        (18, True),
        (99, True),
    ],
)
def test_user_is_adult(age, expected):
    user = user_mod.User("Test User", age)
    assert user.is_adult() is expected


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Alice", "Hello, my name is Alice!"),
        ("", "Hello, my name is !"),
        ("X" * 1000, f"Hello, my name is {'X' * 1000}!"),
    ],
)
def test_user_greet(name, expected):
    user = user_mod.User(name, 25)
    assert user.greet() == expected


@pytest.mark.parametrize(
    "email",
    [
        "alice@example.com",
        "user.name+tag@sub.domain.org",
        "a@b",
    ],
)
def test_user_update_email_valid(email):
    user = user_mod.User("Alice", 30)
    assert user.update_email(email) is None
    assert user.email == email


@pytest.mark.parametrize(
    "email",
    [
        "",
        "invalid",
        "missing-at-sign.com",
        None,
    ],
)
def test_user_update_email_invalid(email):
    user = user_mod.User("Alice", 30)
    with pytest.raises(ValueError, match="Invalid email address"):
        user.update_email(email)


def test_user_update_email_overwrites_existing_email():
    user = user_mod.User("Alice", 30, "old@example.com")
    user.update_email("new@example.com")
    assert user.email == "new@example.com"