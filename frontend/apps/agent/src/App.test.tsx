import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("names the form", () => {
    expect(renderToStaticMarkup(<App />)).toContain("<h1>goldilocks-agent</h1>");
  });
});
