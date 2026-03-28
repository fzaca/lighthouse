function highlightCodeBlocks() {
  document.querySelectorAll('pre code').forEach((block) => {
    const language = block.className.split('language-')[1];
    if (language) {
      block.setAttribute('data-language', language.toUpperCase());
    }
  });
}

document.addEventListener('DOMContentLoaded', highlightCodeBlocks);
