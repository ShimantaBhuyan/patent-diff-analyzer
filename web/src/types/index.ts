export interface Citation {
  source_document_id: string;
  source_document_label: string;
  chunk_id: string;
  exact_quote: string;
  section?: string;
  context_window?: string;
}

export interface DiffResult {
  claim_id: string;
  claim_document_id: string;
  overlap: string;
  differences: string;
  novelty: string;
  risk: 'high' | 'medium' | 'low' | 'unknown';
  confidence: 'high' | 'medium' | 'low' | 'insufficient_evidence';
  citations: Citation[];
  matched_claims: string[];
  reasoning?: string;
}

export interface AuditFinding {
  claim_id: string;
  severity: 'error' | 'warning' | 'info';
  finding_type: string;
  message: string;
  related_citation_ids: string[];
  suggested_action?: string;
}

export interface Document {
  document_id: string;
  label: string;
  filename: string;
  title: string;
  document_type: 'pdf' | 'text';
  raw_text: string;
  upload_timestamp: string;
  parse_warnings: string[];
  metadata: Record<string, unknown>;
}

export interface ClaimSummary {
  claim_id: string;
  document_id: string;
  text: string;
  type: 'independent' | 'dependent';
  dependencies: string[];
}

export interface AnalysisResponse {
  job_id: string;
  status: 'pending' | 'queued' | 'running' | 'completed' | 'failed';
  patent_a_id: string;
  patent_b_id: string;
  patent_a_title: string;
  patent_b_title: string;
  patent_a_claims: ClaimSummary[];
  patent_b_claims: ClaimSummary[];
  results: DiffResult[] | null;
  audit_findings: AuditFinding[] | null;
  error_message?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  saved_name?: string;
  saved_at?: string;
}

export interface SavedAnalysisSummary {
  job_id: string;
  saved_name: string;
  patent_a_id: string;
  patent_b_id: string;
  status: 'pending' | 'queued' | 'running' | 'completed' | 'failed';
  created_at: string;
  saved_at: string;
}
