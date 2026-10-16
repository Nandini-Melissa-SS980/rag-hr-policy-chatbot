import "@testing-library/jest-dom/vitest";

// jsdom implements no layout, so scrollIntoView is missing
// rather than inert. The chat auto-scrolls on every new turn,
// so without this stub any test that renders the transcript
// throws on an unrelated line.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
