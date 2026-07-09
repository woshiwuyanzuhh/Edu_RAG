import { get, del, upload } from './client'
import type { DocumentItem, PaginatedData } from './types'

export function listDocuments(kbId?: number, page = 1, pageSize = 20) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (kbId) params.set('knowledge_base_id', String(kbId))
  return get<PaginatedData<DocumentItem>>(`/documents?${params}`)
}

export function uploadDocument(file: File, knowledgeBaseId: number, docType = 'general') {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('knowledge_base_id', String(knowledgeBaseId))
  fd.append('doc_type', docType)
  return upload<{ doc_id: number; chunk_count: number }>('/documents/upload', fd)
}

export function deleteDocument(id: number) {
  return del<null>(`/documents/${id}`)
}
