// === Generic API Wrapper ===
export interface APIResponse<T = any> {
  success: boolean
  message: string
  data: T
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

// === Knowledge Base ===
export interface KnowledgeBase {
  id: number
  name: string
  description: string
  created_at: string
  updated_at: string
}

export interface KnowledgeBaseCreate {
  name: string
  description?: string
}

// === Document ===
export interface DocumentItem {
  id: number
  filename: string
  file_type: string
  file_size: number
  knowledge_base_id: number
  chunk_count: number
  status: 'processing' | 'done' | 'error'
  created_at: string
}

// === QA ===
export interface QARequest {
  question: string
  knowledge_base_id?: number | null
  top_k?: number
  use_rerank?: boolean
  session_id?: string | null
  history?: { role: string; content: string }[]
}

export interface QAResponse {
  question: string
  answer: string
  sources: SourceItem[]
  session_id?: string | null
}

export interface SourceItem {
  doc_id: number
  chunk_index: number
  score: number
  text_preview: string
}

// === Exam ===
export interface ExamGenerateRequest {
  knowledge_base_id: number
  question_type: 'choice' | 'essay' | 'tf' | 'mixed'
  question_count: number
  difficulty: 'easy' | 'medium' | 'hard'
}

export interface QuestionItem {
  number: number
  type: string
  stem: string
  options?: string[] | null
  answer: string
}

export interface ExamGenerateResponse {
  exam_id: number
  knowledge_base_id: number
  question_type: string
  question_count: number
  questions: QuestionItem[]
}

export interface ExamGradeRequest {
  exam_id: number
  answers: { number: number; answer: string }[]
}

export interface GradeDetail {
  question_number: number
  score: number
  max_score: number
  comment: string
  is_correct: boolean | null
}

export interface DimensionScore {
  concept: number
  analysis: number
  memory: number
  application: number
}

export interface ExamGradeResponse {
  exam_id: number
  total_score: number
  max_score: number
  details: GradeDetail[]
  dimensions?: DimensionScore | null
  summary: string
}

export interface ExamRecord {
  id: number
  knowledge_base_id: number
  question_type: string
  question_count: number
  difficulty: string
  total_score: number | null
  max_score: number | null
  status: 'draft' | 'answered' | 'graded'
  created_at: string
}

export interface ExamRecordDetail extends ExamRecord {
  questions: QuestionItem[]
  answers: { number: number; answer: string }[]
  scores: GradeDetail[]
  dimensions?: DimensionScore | null
}
