import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useSearchParams } from "react-router-dom";
import { vi } from "vitest";
import AssistantPage from "../features/assistant/AssistantPage";
import ReviewsPage from "../features/reviews/ReviewsPage";
import SearchPage from "../features/search/SearchPage";
import { api } from "../lib/api";
import { highlightParts } from "../lib/utils";
import { renderWithProviders } from "./utils";

vi.mock("../lib/api", () => ({
  api: {
    search: vi.fn(), models: vi.fn(), systemModels: vi.fn(), conversations: vi.fn(), conversation: vi.fn(), chat: vi.fn(), chatStream: vi.fn(),
    deleteConversation: vi.fn(), feedback: vi.fn(), reviews: vi.fn(), reviewHistory: vi.fn(), submitReview: vi.fn(),
  },
}));

beforeEach(() => {
  vi.mocked(api.models).mockResolvedValue([{ id: "m", version: "v1", algorithm: "logistic_regression", is_active: true, score_type: "probability_uncalibrated", categories: ["Administration", "Finance and Procurement"], dataset_info: {} as never, created_at: "", headline: { accuracy: 1, macro_f1: 1, weighted_f1: 1, n_evaluated: 1 } }]);
  vi.mocked(api.conversations).mockResolvedValue([]);
  vi.mocked(api.systemModels).mockResolvedValue({ ollama_reachable: false, llm: { model: "llama3.2:3b", available: false }, embedding: { provider: "ollama", model: "nomic-embed-text", dimensions: 768, available: false, note: "" }, classifier: { available: false, version: null }, entity_extraction: { rules: true, spacy: false } });
  vi.mocked(api.reviewHistory).mockResolvedValue([]);
});

test("highlightParts marks matching terms case-insensitively and escapes regex characters", () => {
  expect(highlightParts("The Fleet budget", ["fleet"])).toEqual([{ text: "The ", hit: false }, { text: "Fleet", hit: true }, { text: " budget", hit: false }]);
  expect(highlightParts("a.b", ["a.b"])[0].hit).toBe(true);
});

test("search renders sources, page info and highlighted terms", async () => {
  vi.mocked(api.search).mockResolvedValue({ mode: "hybrid", query: "fleet", total: 1, page: 1, page_size: 10, note: "", results: [{
    chunk_id: "c1", document_id: "d1", filename: "fleet.txt", file_type: "txt", page: null, chunk_index: 0, excerpt: "The fleet budget is 250000.",
    highlights: ["fleet"], score: 0.812, keyword_score: 1, semantic_score: 0.7, category: "Finance and Procurement", created_at: "2025-01-01T00:00:00Z" }] });
  renderWithProviders(<SearchPage />, "/search?q=fleet");
  expect(await screen.findByRole("link", { name: "fleet.txt" })).toHaveAttribute("href", "/documents/d1");
  expect(screen.getByText("page n/a")).toBeInTheDocument();
  expect(screen.getByText("fleet", { selector: "mark" })).toBeInTheDocument();
  expect(screen.getByText("score 0.812")).toBeInTheDocument();
});

test("search shows an empty state and an error state", async () => {
  vi.mocked(api.search).mockResolvedValueOnce({ mode: "hybrid", query: "zzz", total: 0, page: 1, page_size: 10, note: "", results: [] });
  const { unmount } = renderWithProviders(<SearchPage />, "/search?q=zzz");
  expect(await screen.findByText("No matching passages")).toBeInTheDocument();
  unmount();
  vi.mocked(api.search).mockRejectedValueOnce(new Error("The vector database is unavailable."));
  renderWithProviders(<SearchPage />, "/search?q=again");
  expect(await screen.findByRole("alert")).toHaveTextContent("vector database is unavailable");
});

test("search box follows ?q= when the URL changes while the page is mounted (header search)", async () => {
  vi.mocked(api.search).mockResolvedValue({ mode: "hybrid", query: "x", total: 0, page: 1, page_size: 10, note: "", results: [] });
  function HeaderSearch() {
    const [, setParams] = useSearchParams();
    return <button onClick={() => setParams({ q: "second query" })}>header search</button>;
  }
  renderWithProviders(<><HeaderSearch /><SearchPage /></>, "/search?q=first");
  expect(await screen.findByDisplayValue("first")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "header search" }));
  expect(await screen.findByDisplayValue("second query")).toBeInTheDocument();
});

test("assistant warns when the LLM is unavailable and surfaces chat errors with retry", async () => {
  vi.mocked(api.chatStream).mockRejectedValue(new Error("Ollama is not reachable. Start Ollama and pull the configured models."));
  renderWithProviders(<AssistantPage />);
  expect(await screen.findByText(/is not available/)).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Question"), "What is the budget?");
  await userEvent.click(screen.getByRole("button", { name: /Send/ }));
  expect(await screen.findByText(/Ollama is not reachable\. Start Ollama/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(api.chatStream).toHaveBeenCalledTimes(2));
});

const DONE = { conversation_id: "c1", retrieval_mode: "hybrid", excluded_suspicious: 0, inference: "", message: { id: "m1", role: "assistant" as const, content: "x", citations: [], sufficient_evidence: true, latency_ms: 1, feedback: null, created_at: "" } };
const SAVED_THREAD = { id: "c1", title: "t", created_at: "", updated_at: "", messages: [
  { id: "m0", role: "user" as const, content: "Budget?", citations: [], sufficient_evidence: null, latency_ms: null, feedback: null, created_at: "" },
  { id: "m1", role: "assistant" as const, content: "The budget is 250000.", citations: [{ document_id: "d1", filename: "fleet.txt", page: null, chunk_id: "c", excerpt: "budget is 250000" }], sufficient_evidence: true, latency_ms: 1200, feedback: null, created_at: "" }] };

test("assistant renders the answer and citation links", async () => {
  vi.mocked(api.chatStream).mockImplementation(async (_q, _id, onEvent) => { onEvent({ type: "done", data: DONE }); });
  vi.mocked(api.conversation).mockResolvedValue(SAVED_THREAD);
  renderWithProviders(<AssistantPage />);
  await userEvent.type(await screen.findByLabelText("Question"), "Budget?");
  await userEvent.click(screen.getByRole("button", { name: /Send/ }));
  expect(await screen.findByText("The budget is 250000.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /fleet.txt · page unavailable/ })).toHaveAttribute("href", "/documents/d1");
});

test("assistant shows the answer as it streams, then swaps in the saved message", async () => {
  let finish!: () => void;
  vi.mocked(api.chatStream).mockImplementation((_q, _id, onEvent) => new Promise<void>((resolve) => {
    onEvent({ type: "meta", data: { retrieval_mode: "hybrid", excluded_suspicious: 0 } });
    onEvent({ type: "citations", data: [{ document_id: "d1", filename: "fleet.txt", page: null, chunk_id: "c", excerpt: "budget is 250000" }] });
    onEvent({ type: "delta", data: { text: "The budget " } });
    onEvent({ type: "delta", data: { text: "is 250" } });
    finish = () => { onEvent({ type: "done", data: DONE }); resolve(); };
  }));
  vi.mocked(api.conversation).mockResolvedValue(SAVED_THREAD);
  renderWithProviders(<AssistantPage />);
  await userEvent.type(await screen.findByLabelText("Question"), "Budget?");
  await userEvent.click(screen.getByRole("button", { name: /Send/ }));
  // partial text and its validated source are visible while the model is still writing, with a way to stop
  expect(await screen.findByText("The budget is 250")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /fleet.txt · page unavailable/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Stop/ })).toBeInTheDocument();
  finish();
  expect(await screen.findByText("The budget is 250000.")).toBeInTheDocument(); // the saved message replaced the stream
  expect(screen.queryByText("The budget is 250")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Stop/ })).not.toBeInTheDocument();
});

test("stopping a stream shows a note instead of an error", async () => {
  vi.mocked(api.chatStream).mockImplementation((_q, _id, _onEvent, signal) => new Promise<void>((_, reject) => {
    signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
  }));
  renderWithProviders(<AssistantPage />);
  await userEvent.type(await screen.findByLabelText("Question"), "Budget?");
  await userEvent.click(screen.getByRole("button", { name: /Send/ }));
  await userEvent.click(await screen.findByRole("button", { name: /Stop/ }));
  expect(await screen.findByText(/Stopped\. This question and the partial answer were not saved/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument(); // not treated as a failure
  expect(screen.queryByText(/aborted/i)).not.toBeInTheDocument();
});

test("review submission sends a correction with the chosen category and note", async () => {
  vi.mocked(api.reviews).mockResolvedValue({ total: 1, items: [{ document_id: "d1", filename: "memo.txt", predicted_category: "Administration", score: 0.4, score_type: "probability_uncalibrated", model_version: "v1", text_preview: "preview", created_at: "2025-01-01T00:00:00Z" }] });
  vi.mocked(api.submitReview).mockResolvedValue({});
  renderWithProviders(<ReviewsPage />);
  expect(await screen.findByRole("button", { name: "Confirm prediction" })).toBeInTheDocument();
  await userEvent.selectOptions(await screen.findByLabelText("Category for memo.txt"), "Finance and Procurement");
  await userEvent.type(screen.getByLabelText(/Note/), "it is an invoice");
  await userEvent.click(screen.getByRole("button", { name: "Correct label" }));
  await waitFor(() => expect(api.submitReview).toHaveBeenCalledWith("d1", { decision: "correct", category: "Finance and Procurement", note: "it is an invoice" }));
});
