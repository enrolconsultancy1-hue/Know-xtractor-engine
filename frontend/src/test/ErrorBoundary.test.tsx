import React, { useState } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ErrorBoundary from "../components/ErrorBoundary";

// Component that throws on demand
function ProblemChild({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error("Simulated component failure");
  }
  return <div>Normal Content Loaded</div>;
}

describe("ErrorBoundary", () => {
  // Suppress console.error during throwing tests
  const originalError = console.error;
  beforeEach(() => {
    console.error = vi.fn();
  });
  afterEach(() => {
    console.error = originalError;
  });

  it("renders children without error", () => {
    render(
      <ErrorBoundary>
        <ProblemChild shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText("Normal Content Loaded")).toBeInTheDocument();
  });

  it("catches errors and displays fallback UI", () => {
    render(
      <ErrorBoundary>
        <ProblemChild shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText(/Simulated component failure/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders custom fallback prop when provided", () => {
    render(
      <ErrorBoundary fallback={<div data-testid="custom-fallback">Custom Fallback UI</div>}>
        <ProblemChild shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByTestId("custom-fallback")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });

  it("calls onReset callback and can recover on Try Again", () => {
    const onReset = vi.fn();

    function RecoverableContainer() {
      const [hasError, setHasError] = useState(true);
      return (
        <div>
          <button onClick={() => setHasError(false)}>Fix Error</button>
          <ErrorBoundary onReset={() => { onReset(); setHasError(false); }}>
            <ProblemChild shouldThrow={hasError} />
          </ErrorBoundary>
        </div>
      );
    }

    render(<RecoverableContainer />);

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    const tryAgainBtn = screen.getByRole("button", { name: /try again/i });
    fireEvent.click(tryAgainBtn);

    expect(onReset).toHaveBeenCalled();
    expect(screen.getByText("Normal Content Loaded")).toBeInTheDocument();
  });
});
