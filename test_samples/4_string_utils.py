def reverse_string(s: str) -> str:
    return s[::-1]

def is_palindrome(s: str) -> bool:
    cleaned = s.lower().replace(" ", "")
    return cleaned == cleaned[::-1]

def count_words(text: str) -> int:
    return len(text.split())

def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + suffix

def capitalize_words(text: str) -> str:
    return " ".join(word.capitalize() for word in text.split())
