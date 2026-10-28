import { vi } from "vitest";
import { ApiError, api } from "../lib/api";
import type { ChatStreamEvent } from "../types";

const enc = new TextEncoder();

/** A fetch response whose body arrives in the given byte chunks, like a real network stream. */
function streamResponse(chunks: Uint8Array[], init: ResponseInit = { status: 200 }) {
  const body = new ReadableStream<Uint8Array>({
    start(controller) { chunks.forEach((c) => controller.enqueue(c)); controller.close(); },
  });
  return new Response(body, { ...init, headers: { "Content-Type": "text/event-stream" } });
}
const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
const DONE = { conversation_id: "c1", retrieval_mode: "hybrid", excluded_suspicious: 0, inference: "", message: { id: "m", role: "assistant", content: "ok", citations: [], sufficient_evidence: true, latency_ms: 1, feedback: null, created_at: "" } };

async function collect(response: Response) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
  const events: ChatStreamEvent[] = [];
  await api.chatStream("q", undefined, (e) => events.push(e));
  return events;
}

afterEach(() => vi.unstubAllGlobals());

test("parses events split across arbitrary chunk boundaries, including inside multi-byte characters", async () => {
  const bytes = enc.encode(sse("meta", { retrieval_mode: "hybrid", excluded_suspicious: 0 }) + sse("delta", { text: "café \u{1F600}" }) + sse("done", DONE));
  const chunks = Array.from({ length: Math.ceil(bytes.length / 5) }, (_, i) => bytes.slice(i * 5, i * 5 + 5)); // 5-byte chunks cut UTF-8 sequences
  const events = await collect(streamResponse(chunks));
  expect(events.map((e) => e.type)).toEqual(["meta", "delta", "done"]);
  expect(events[1]).toEqual({ type: "delta", data: { text: "café \u{1F600}" } });
});

test("sends the bearer token and JSON body to /chat/stream", async () => {
  localStorage.setItem("infomind.token", "tok");
  const fetchMock = vi.fn().mockResolvedValue(streamResponse([enc.encode(sse("done", DONE))]));
  vi.stubGlobal("fetch", fetchMock);
  await api.chatStream("What?", "conv-1", () => {});
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/v1/chat/stream");
  expect(new Headers(init.headers).get("Authorization")).toBe("Bearer tok");
  expect(JSON.parse(init.body)).toEqual({ question: "What?", conversation_id: "conv-1" });
  localStorage.removeItem("infomind.token");
});

test("an error event rejects with the server's message and status", async () => {
  const promise = collect(streamResponse([enc.encode(sse("meta", { retrieval_mode: "hybrid", excluded_suspicious: 0 }) + sse("error", { message: "Ollama is not reachable.", status: 503 }))]));
  await expect(promise).rejects.toMatchObject({ message: "Ollama is not reachable.", status: 503 });
});

test("a connection that closes before the done event is reported, not silently accepted", async () => {
  const promise = collect(streamResponse([enc.encode(sse("delta", { text: "partial" }))]));
  await expect(promise).rejects.toThrow(/closed before the answer finished/);
});

test("HTTP errors before streaming starts use the standard error format", async () => {
  const res = new Response(JSON.stringify({ error: { message: "Conversation not found", request_id: "r1" } }), { status: 404 });
  const promise = collect(res);
  await expect(promise).rejects.toBeInstanceOf(ApiError);
  await expect(collect(new Response(JSON.stringify({ error: { message: "Conversation not found" } }), { status: 404 }))).rejects.toMatchObject({ status: 404, message: "Conversation not found" });
});

test("an API base polluted with a byte-order mark, spaces or a trailing slash is cleaned, not treated as a relative path", async () => {
  vi.stubEnv("VITE_API_BASE", "﻿ https://api.example.com/api/v1/ ");
  vi.resetModules();
  const { api: fresh } = await import("../lib/api");
  const fetchMock = vi.fn().mockResolvedValue(streamResponse([enc.encode(sse("done", DONE))]));
  vi.stubGlobal("fetch", fetchMock);
  await fresh.chatStream("q", undefined, () => {});
  expect(fetchMock.mock.calls[0][0]).toBe("https://api.example.com/api/v1/chat/stream");
  vi.unstubAllEnvs();
});

test("an unreachable server gives the friendly message", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
  await expect(api.chatStream("q", undefined, () => {})).rejects.toMatchObject({ status: 0, message: expect.stringContaining("Cannot reach the server") });
});
