const BRAND_BUBBLE_PHRASES = {
    hero: [
        "What are we building today?",
        "Where do we start?",
        "Which repo goes first?",
        "Ready for a calmer run?",
        "What are we testing next?",
    ],
    sidebar: [
        "What are we building?",
        "Want to run some tests?",
        "What are we checking?",
        "Where to next?",
        "Ready for another run?",
    ],
};

function bubblePhrasePool(context) {
    return BRAND_BUBBLE_PHRASES[context] || BRAND_BUBBLE_PHRASES.sidebar;
}

function pickBrandBubblePhrase(context, previous = "") {
    const phrases = bubblePhrasePool(context);
    const options = phrases.filter((phrase) => phrase !== previous);
    const pool = options.length ? options : phrases;
    return pool[Math.floor(Math.random() * pool.length)];
}

function swapBubblePhrase(bubble) {
    const context = bubble.dataset.bubbleContext || "sidebar";
    bubble.classList.add("is-updating");

    window.setTimeout(() => {
        bubble.textContent = pickBrandBubblePhrase(context, bubble.textContent);
        bubble.classList.remove("is-updating");
    }, 120);
}

function renderBrandBubbles() {
    document.querySelectorAll(".brand-bubble").forEach((bubble, index) => {
        const context = bubble.dataset.bubbleContext || "sidebar";
        bubble.textContent = pickBrandBubblePhrase(context, bubble.textContent);

        if (bubble.dataset.rotating === "true") return;
        bubble.dataset.rotating = "true";

        const delay = 5600 + index * 900;
        window.setInterval(() => {
            swapBubblePhrase(bubble);
        }, delay);
    });
}

document.addEventListener("DOMContentLoaded", renderBrandBubbles);
