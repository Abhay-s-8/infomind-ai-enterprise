import { fireEvent, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import DocumentsPage from "../features/documents/DocumentsPage";
import { api } from "../lib/api";
import { validateFile } from "../lib/utils";
import type { DocumentItem } from "../types";
import { renderWithProviders } from "./utils";

vi.mock("../lib/api", () => ({ api: { documents: vi.fn(), upload: vi.fn() } }));

const doc = (over: Partial<DocumentItem> = {}): DocumentItem => ({
  id: "d1", filename: "report.pdf", extension: "pdf", mime_type: "application/pdf", size_bytes: 2048, sha256: "x", status: "completed",
  error_message: null, page_count: 2, chunk_count: 3, is_demo: false, deletion_state: "active", owner_id: "u", created_at: "2025-01-01T00:00:00Z",
  prediction: null, verified_category: "Administration", category: "Administration", ...over,
});

test("validateFile rejects unsupported, empty and oversized files", () => {
  expect(validateFile(new File(["x"], "run.exe"))).toMatch(/Unsupported/);
  expect(validateFile(new File([], "a.txt"))).toBe("The file is empty.");
  const big = new File(["x"], "big.pdf");
  Object.defineProperty(big, "size", { value: 26 * 1024 * 1024 });
  expect(validateFile(big)).toMatch(/limit/);
  expect(validateFile(new File(["x"], "ok.docx"))).toBeNull();
});

test("lists documents with status, category and verified marker", async () => {
  vi.mocked(api.documents).mockResolvedValue({ items: [doc(), doc({ id: "d2", filename: "bad.txt", status: "failed", category: null, verified_category: null })], total: 2, page: 1, page_size: 15 });
  renderWithProviders(<DocumentsPage />);
  expect(await screen.findByRole("link", { name: "report.pdf" })).toHaveAttribute("href", "/documents/d1");
  expect(screen.getByText("failed", { selector: "span" })).toBeInTheDocument();
  expect(screen.getByTitle("Human verified")).toBeInTheDocument();
});

test("shows an empty state when no documents match", async () => {
  vi.mocked(api.documents).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 15 });
  renderWithProviders(<DocumentsPage />);
  expect(await screen.findByText("No documents found")).toBeInTheDocument();
});

test("rejects an invalid file client-side without calling the upload API", async () => {
  vi.mocked(api.documents).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 15 });
  renderWithProviders(<DocumentsPage />);
  const input = await screen.findByTestId("file-input");
  fireEvent.change(input, { target: { files: [new File(["MZ"], "malware.exe")] } });
  expect(await screen.findByText(/malware.exe: Unsupported type/)).toBeInTheDocument();
  expect(api.upload).not.toHaveBeenCalled();
});

test("uploads a valid file and reports the per-file server result", async () => {
  vi.mocked(api.documents).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 15 });
  vi.mocked(api.upload).mockResolvedValue({ results: [{ document: doc(), duplicate: false }], errors: [{ filename: "b.txt", error: "The file is empty." }] });
  renderWithProviders(<DocumentsPage />);
  const input = await screen.findByTestId("file-input");
  fireEvent.change(input, { target: { files: [new File(["hello"], "a.txt", { type: "text/plain" })] } });
  await waitFor(() => expect(api.upload).toHaveBeenCalled());
  expect(await screen.findByText(/report.pdf: uploaded, processing started/)).toBeInTheDocument();
  expect(screen.getByText("b.txt: The file is empty.")).toBeInTheDocument();
});
