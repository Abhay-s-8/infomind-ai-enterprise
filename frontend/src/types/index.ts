export type Role = "admin" | "analyst" | "reviewer";

export interface User { id: string; email: string; full_name: string; role: Role; is_active: boolean; created_at: string }

export interface Prediction {
  id: string; category: string; score: number; score_type: "probability_uncalibrated" | "decision_score";
  all_scores: Record<string, number>; model_version: string; review_status: string; created_at: string;
}

export interface DocumentItem {
  id: string; filename: string; extension: string; mime_type: string; size_bytes: number; sha256: string;
  status: string; error_message: string | null; page_count: number | null; chunk_count: number; is_demo: boolean;
  deletion_state: string; owner_id: string; created_at: string; prediction: Prediction | null;
  verified_category: string | null; category: string | null;
}

export interface DocEvent { stage: string; message: string; created_at: string }
export interface Entity { id: string; text: string; label: string; method: string }
export interface DocumentDetail extends DocumentItem { text_preview: string; events: DocEvent[]; entities: Entity[]; indexed: boolean }
export interface DocumentList { items: DocumentItem[]; total: number; page: number; page_size: number }
export interface UploadBatch {
  results: { document: DocumentItem; duplicate: boolean }[];
  errors: { filename: string; error: string }[];
}

export interface SearchHit {
  chunk_id: string; document_id: string; filename: string; file_type: string; page: number | null; chunk_index: number;
  excerpt: string; highlights: string[]; score: number; keyword_score: number; semantic_score: number | null;
  category: string | null; created_at: string;
}
export interface SearchResponse { mode: string; query: string; total: number; page: number; page_size: number; results: SearchHit[]; note: string }
export type SearchMode = "keyword" | "semantic" | "hybrid";

export interface Citation { document_id: string; filename: string; page: number | null; chunk_id: string; excerpt: string; score?: number | null }
export interface Message {
  id: string; role: "user" | "assistant"; content: string; citations: Citation[]; sufficient_evidence: boolean | null;
  latency_ms: number | null; feedback: string | null; created_at: string;
}
export interface Conversation { id: string; title: string; created_at: string; updated_at: string }
export interface ConversationDetail extends Conversation { messages: Message[] }
export interface ChatResponse { conversation_id: string; message: Message; retrieval_mode: string; excluded_suspicious: number; inference: string }
/** Server-Sent Events from POST /chat/stream. `delta` text is provisional; `done` carries the stored, validated message. */
export type ChatStreamEvent =
  | { type: "meta"; data: { retrieval_mode: string; excluded_suspicious: number } }
  | { type: "citations"; data: Citation[] }
  | { type: "delta"; data: { text: string } }
  | { type: "done"; data: ChatResponse }
  | { type: "error"; data: { message: string; status: number } };

export interface Overview {
  totals: { documents: number; completed: number; pending: number; failed: number; pending_reviews: number | null };
  processing_success_rate: number | null;
  by_status: Record<string, number>;
  classification_distribution: Record<string, number>;
  recent_uploads: { id: string; filename: string; status: string; created_at: string; is_demo: boolean }[];
  recent_searches: { query: string; mode: string; results: number; created_at: string }[];
  recent_questions: { question: string; created_at: string }[];
  has_demo_data: boolean;
  system: { status: string; database: { ok: boolean }; vector_store: { ok: boolean }; ollama: { ok: boolean }; llm_available: boolean; embedding_available: boolean };
}

export interface ClassMetrics { precision: number; recall: number; f1: number; support: number }
export interface EvalMetrics {
  n_evaluated: number; accuracy: number; macro_precision: number; macro_recall: number; macro_f1: number; weighted_f1: number;
  per_class: Record<string, ClassMetrics>; confusion_matrix: { labels: string[]; matrix: number[][] };
}
export interface ModelInfo {
  id: string; version: string; algorithm: string; is_active: boolean; score_type: string; categories: string[];
  dataset_info: Record<string, unknown> & { total: number; train: number; validation: number; test: number; name: string; caveat: string; trained_at: string; selection_criterion: string; evaluation_split: string };
  created_at: string; headline: { accuracy: number; macro_f1: number; weighted_f1: number; n_evaluated: number };
  metrics?: EvalMetrics; comparison?: Record<string, { test: EvalMetrics; validation?: EvalMetrics }>;
}

export interface ReviewItem {
  document_id: string; filename: string; predicted_category: string | null; score: number | null;
  score_type: string | null; model_version: string | null; text_preview: string; created_at: string;
}

export interface AuditEvent { id: string; created_at: string; actor_id: string | null; action: string; target_type: string | null; target_id: string | null; outcome: string; request_id: string | null; detail: string | null }

export interface SystemModels {
  ollama_reachable: boolean; llm: { model: string; available: boolean };
  embedding: { provider: string; model: string; dimensions: number; available: boolean; note: string };
  classifier: { available: boolean; version: string | null }; entity_extraction: { rules: boolean; spacy: boolean };
}

export interface DocumentsAnalytics {
  uploads_over_time: { date: string; count: number }[]; by_file_type: { type: string; count: number }[];
  by_category: { category: string; count: number }[]; avg_processing_ms: number | null; processing_jobs_measured: number;
}
export interface ClassificationAnalytics {
  pending_reviews: number;
  model: null | { version: string; algorithm: string; trained_at: string; dataset_size: number; synthetic_data: boolean;
    comparison: Record<string, { macro_f1: number; accuracy: number; weighted_f1: number }>;
    per_class_f1: Record<string, number>; confusion_matrix: { labels: string[]; matrix: number[][] } };
}
export interface SearchAnalytics {
  searches_per_day: { date: string; count: number }[];
  by_mode: { mode: string; count: number; avg_latency_ms: number | null }[];
  retrieval_evaluation: null | { created_at: string; synthetic: boolean; k: number; n_queries: number; corpus: string; metrics: Record<string, Record<string, number>> };
}
