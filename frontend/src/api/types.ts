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

// === Document Types ===
// 与后端 src/shared/constants.py 的 DOCUMENT_TYPES 保持一致
export interface DocTypeOption {
  key: string
  label: string
  description: string
}

export const DOCUMENT_TYPES: DocTypeOption[] = [
  { key: 'general',    label: '通用',     description: '默认清洗策略，适用于未分类的文档' },
  { key: 'education',  label: '教育',     description: '教材、讲义、试题 — 过滤页码、水印、参考文献' },
  { key: 'gaming',     label: '游戏攻略',  description: '论坛攻略、wiki — 过滤签名、广告、纯 emoji' },
  { key: 'tech',       label: '技术文档',  description: 'IT/编程/软件手册 — 过滤代码行号、shell 提示符、TODO 注释' },
  { key: 'medical',    label: '医疗健康',  description: '医学文献、健康科普 — 过滤免责声明、医院信息、广告' },
  { key: 'legal',      label: '法律法规',  description: '法条、判例、合同 — 过滤页眉页脚、司法解释水印' },
  { key: 'finance',    label: '金融财经',  description: '研报、财报、理财 — 过滤风险提示、免责声明、股票代码刷屏' },
  { key: 'news',       label: '新闻资讯',  description: '新闻报道、资讯 — 过滤版权声明、记者署名、编辑信息' },
  { key: 'literature', label: '文学作品',  description: '小说、散文、诗歌 — 过滤 OCR 噪声、章节编号噪声，保留对话' },
  { key: 'business',   label: '商业管理',  description: '商业报告、管理文档 — 过滤 PPT 页码、机密水印、页眉页脚' },
]

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

export interface FeedbackRequest {
  question: string
  answer: string
  rating: 'like' | 'dislike'
  comment?: string
  sources?: SourceItem[]
}

export interface FeedbackResponse {
  id: number
}
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
