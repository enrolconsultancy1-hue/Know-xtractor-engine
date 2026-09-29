import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="card" style={{ border: "1px solid var(--red)", margin: "20px 0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
            <span style={{ fontSize: "24px" }}>⚠️</span>
            <div>
              <h3 style={{ margin: 0, color: "var(--red)" }}>Something went wrong</h3>
              <p className="subtitle" style={{ margin: "4px 0 0" }}>
                An unexpected error occurred in this view.
              </p>
            </div>
          </div>
          {this.state.error && (
            <pre
              style={{
                background: "var(--panel-2)",
                padding: "12px",
                borderRadius: "6px",
                fontSize: "12px",
                overflowX: "auto",
                color: "#ff8b94",
                margin: "12px 0",
              }}
            >
              {this.state.error.message || String(this.state.error)}
            </pre>
          )}
          <div style={{ display: "flex", gap: "10px", marginTop: "16px" }}>
            <button
              className="btn btn-primary"
              onClick={this.handleReset}
              style={{ background: "var(--accent)" }}
            >
              Try Again
            </button>
            <button
              className="btn"
              onClick={() => window.location.reload()}
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
