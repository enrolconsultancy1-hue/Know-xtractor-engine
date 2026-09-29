import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Sidebar, { PageKey } from "../components/sidebar";

describe("Sidebar", () => {
  it("renders brand and navigation items", () => {
    const setPage = vi.fn();
    render(<Sidebar page="dashboard" setPage={setPage} project={null} />);

    expect(screen.getByText("KNOX")).toBeInTheDocument();
    expect(screen.getByText("Knowledge eXtraction")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Settings / Auth")).toBeInTheDocument();
  });

  it("marks active page button with active class", () => {
    const setPage = vi.fn();
    render(<Sidebar page="architecture" setPage={setPage} project={null} />);

    const archBtn = screen.getByText("Architecture").closest("button");
    const dashBtn = screen.getByText("Dashboard").closest("button");

    expect(archBtn).toHaveClass("active");
    expect(dashBtn).not.toHaveClass("active");
  });

  it("calls setPage when nav item is clicked", () => {
    const setPage = vi.fn();
    render(<Sidebar page="dashboard" setPage={setPage} project={null} />);

    fireEvent.click(screen.getByText("Settings / Auth"));
    expect(setPage).toHaveBeenCalledWith("settings");
  });

  it("displays project name and id when project is selected", () => {
    const setPage = vi.fn();
    render(
      <Sidebar
        page="repository"
        setPage={setPage}
        project={{ id: 42, name: "AlphaProject" }}
      />
    );

    expect(screen.getByText("AlphaProject")).toBeInTheDocument();
    expect(screen.getByText("#42")).toBeInTheDocument();
  });
});
