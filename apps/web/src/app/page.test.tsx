import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import HomePage from "./page";

describe("HomePage", () => {
  it("presents the document similarity workflow", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { name: /metin benzerliğini kanıtlarıyla incele/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(3);
    expect(screen.getByRole("link", { name: /^belge yükle$/i })).toHaveAttribute(
      "href",
      "#belge-yukle",
    );
    expect(screen.getByText(/oturum kontrol ediliyor/i)).toBeInTheDocument();
  });
});
