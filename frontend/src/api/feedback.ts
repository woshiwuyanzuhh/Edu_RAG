import { post } from './client'
import type { FeedbackRequest, FeedbackResponse } from './types'

export function sendFeedback(params: FeedbackRequest) {
  return post<FeedbackResponse>('/qa/feedback', params)
}
