class User:
    def __init__(self, name: str, age: int, email: str = ""):
        self.name = name
        self.age = age
        self.email = email

    def is_adult(self) -> bool:
        return self.age >= 18

    def greet(self) -> str:
        return f"Hello, my name is {self.name}!"

    def update_email(self, email: str) -> None:
        if "@" not in email:
            raise ValueError("Invalid email address")
        self.email = email

    def to_dict(self) -> dict:
        return {"name": self.name, "age": self.age, "email": self.email}
