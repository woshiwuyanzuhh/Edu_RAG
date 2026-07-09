import { get, post, del } from './client'
import type { KnowledgeBase, KnowledgeBaseCreate, PaginatedData } from './types'

export function listKnowledgeBases(page = 1, pageSize = 20) {
  return get<PaginatedData<KnowledgeBase>>(`/kb?page=${page}&page_size=${pageSize}`)
}

export function createKnowledgeBase(data: KnowledgeBaseCreate) {
  return post<{ id: number; name: string }>('/kb', data)
}

export function deleteKnowledgeBase(id: number) {
  return del<null>(`/kb/${id}`)
}
