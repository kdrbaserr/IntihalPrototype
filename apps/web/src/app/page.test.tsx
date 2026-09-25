import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";

describe("HomePage", () => {
  it("presents the document similarity workflow", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { name: /metin benzerliğini kanıtlarıyla incele/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(3);
    expect(screen.getByRole("button", { name: /belge yükleme yakında/i })).toBeDisabled();
  });
});
