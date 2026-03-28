let EXAMPLES = [];

fetch("/static/data/examples.json")
    .then(r => r.json())
    .then(data => { EXAMPLES = data; });

function loadExample(index) {
    const example = EXAMPLES[index];
    document.getElementById("code").value = example.code;
    generate();
}
