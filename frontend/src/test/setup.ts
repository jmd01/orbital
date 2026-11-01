import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// framer-motion calls this when measuring height: "auto" rows; jsdom has no layout and logs an error.
window.scrollTo = () => {};

// Testing Library only cleans up on its own when test globals are enabled, and they are not.
afterEach(() => {
	cleanup();
});
