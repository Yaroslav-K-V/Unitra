const EXAMPLES = [
    {
        label: "Simple function",
        code: `def add(a: int, b: int) -> int:
    return a + b

def multiply(a: int, b: int) -> int:
    return a * b`
    },
    {
        label: "Class",
        code: `class BankAccount:
    def __init__(self, owner: str, balance: float = 0.0):
        self.owner = owner
        self.balance = balance

    def deposit(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        self.balance += amount
        return self.balance

    def withdraw(self, amount: float) -> float:
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        self.balance -= amount
        return self.balance`
    },
    {
        label: "With exceptions",
        code: `def divide(a: float, b: float) -> float:
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b

def parse_age(value: str) -> int:
    age = int(value)
    if age < 0 or age > 150:
        raise ValueError(f"Invalid age: {age}")
    return age`
    }
];

function loadExample(index) {
    const example = EXAMPLES[index];
    document.getElementById("code").value = example.code;
    generate();
}
