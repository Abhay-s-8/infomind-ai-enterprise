import { screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { vi } from "vitest";
import DashboardPage from "../features/dashboard/DashboardPage";
import { api } from "../lib/api";
import type { Overview } from "../types";
import { renderWithProviders } from "./utils";

vi.mock("../lib/api", () => ({ api: { overview: vi.fn() } }));
vi.mock("recharts", () => {
  const Stub = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
  return { ResponsiveContainer: Stub, PieChart: Stub, Pie: Stub, Cell: Stub, BarChart: Stub, Bar: Stub, CartesianGrid: Stub, XAxis: Stub, YAxis: Stub, Tooltip: Stub };
});

const base: Overview = {
  totals: { documents: 0, completed: 0, pending: 0, failed: 0, pending_reviews: null }, processing_success_rate: null,
  by_status: {}, classification_distribution: {}, recent_uploads: [], recent_searches: [], recent_questions: [], has_demo_data: false,
  system: { status: "ready", database: { ok: true }, vector_store: { ok: true }, ollama: { ok: false }, llm_available: false, embedding_available: false },
};

test("shows a loading state, then an honest empty state", async () => {
  vi.mocked(api.overview).mockResolvedValue(base);
  renderWithProviders(<DashboardPage />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading overview");
  expect(await screen.findByText("No documents yet")).toBeInTheDocument();
  expect(screen.getByText("n/a")).toBeInTheDocument(); // success rate is not fabricated
  expect(screen.getByText(/Ollama: unavailable/)).toBeInTheDocument();
});

test("renders real figures when documents exist", async () => {
  vi.mocked(api.overview).mockResolvedValue({
    ...base, totals: { documents: 12, completed: 9, pending: 1, failed: 2, pending_reviews: null }, processing_success_rate: 9 / 11,
    recent_uploads: [{ id: "1", filename: "budget.pdf", status: "completed", created_at: "2025-01-01T00:00:00Z", is_demo: false }],
  });
  renderWithProviders(<DashboardPage />);
  expect(await screen.findByText("12")).toBeInTheDocument();
  expect(screen.getByText("81.8%")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "budget.pdf" })).toHaveAttribute("href", "/documents/1");
});

test("shows an error with retry when the API fails", async () => {
  vi.mocked(api.overview).mockRejectedValue(new Error("Cannot reach the server. Is the backend running?"));
  renderWithProviders(<DashboardPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
});
