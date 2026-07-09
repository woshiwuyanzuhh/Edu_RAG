import { get, post } from './client'
import type {
  ExamGenerateRequest,
  ExamGenerateResponse,
  ExamGradeRequest,
  ExamGradeResponse,
  ExamRecord,
  ExamRecordDetail,
  PaginatedData,
} from './types'

export function generateExam(data: ExamGenerateRequest) {
  return post<ExamGenerateResponse>('/exam/generate', data)
}

export function gradeExam(data: ExamGradeRequest) {
  return post<ExamGradeResponse>('/exam/grade', data)
}

export function listExamRecords(kbId?: number, page = 1, pageSize = 20) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (kbId) params.set('knowledge_base_id', String(kbId))
  return get<PaginatedData<ExamRecord>>(`/exam/records?${params}`)
}

export function getExamRecord(id: number) {
  return get<ExamRecordDetail>(`/exam/records/${id}`)
}
