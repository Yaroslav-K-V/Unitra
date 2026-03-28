function getGreeting() {
    const hour = new Date().getHours();
    const pick = arr => arr[Math.floor(Math.random() * arr.length)];

    if (hour >= 5 && hour < 12)  return pick(["Good morning", "Rise and shine", "Morning"]);
    if (hour >= 12 && hour < 17) return pick(["Good afternoon", "Hey there", "Hello"]);
    if (hour >= 17 && hour < 22) return pick(["Good evening", "Evening", "Welcome back"]);
    return pick(["Good night", "Burning the midnight oil?", "Late night session"]);
}

function renderGreeting(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = getGreeting();
}
