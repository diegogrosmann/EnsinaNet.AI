// accounts/static/accounts/js/easymde_init.js

document.addEventListener('DOMContentLoaded', function() {
    var textareas = document.querySelectorAll('.easymde');
    textareas.forEach(function(textarea) {
        new EasyMDE({
            element: textarea,
            spellChecker: false,
            toolbar: [
                "bold", "italic", "heading", "|",
                "quote", "unordered-list", "ordered-list", "|",
                "preview", "side-by-side", "fullscreen", "|",
                "guide"
            ],
            autosave: {
                enabled: false,
            },
            status: false,
            renderingConfig: {
                singleLineBreaks: false,
                codeSyntaxHighlighting: true,
            },
            placeholder: "Digite seu texto em Markdown aqui...",
        });
    });
});
