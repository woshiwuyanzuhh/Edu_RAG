<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { EditOutlined, ThunderboltOutlined, CheckOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { listKnowledgeBases } from '../api/knowledge'
import { generateExam, gradeExam, listExamRecords, getExamRecord } from '../api/exam'
import type { KnowledgeBase, QuestionItem, ExamRecord, GradeDetail, DimensionScore } from '../api/types'
import { message } from 'ant-design-vue'

const kbList = ref<KnowledgeBase[]>([])
const selectedKbId = ref<number | undefined>()
const questionType = ref('mixed')
const questionCount = ref(5)
const difficulty = ref('medium')
const generating = ref(false)

const currentExamId = ref<number | null>(null)
const questions = ref<QuestionItem[]>([])
const examType = ref('')

const answers = ref<Record<number, string>>({})
const grading = ref(false)

const gradeResult = ref<{
  total_score: number; max_score: number; summary: string
  details: GradeDetail[]; dimensions?: DimensionScore | null
} | null>(null)

const records = ref<ExamRecord[]>([])
const recordsLoading = ref(false)

async function loadKBs() {
  try { const data = await listKnowledgeBases(1, 100); kbList.value = data.items } catch {}
}

async function handleGenerate() {
  if (!selectedKbId.value) return message.warning('请选择知识库')
  generating.value = true
  try {
    const data = await generateExam({
      knowledge_base_id: selectedKbId.value,
      question_type: questionType.value as any,
      question_count: questionCount.value,
      difficulty: difficulty.value as any,
    })
    currentExamId.value = data.exam_id
    questions.value = data.questions
    examType.value = data.question_type
    answers.value = {}
    gradeResult.value = null
    message.success(`成功生成 ${data.question_count} 道题目`)
  } catch (e: any) { message.error(e.message) }
  finally { generating.value = false }
}

async function handleGrade() {
  if (!currentExamId.value) return
  const answerList = Object.entries(answers.value)
    .filter(([, v]) => v.trim())
    .map(([number, answer]) => ({ number: parseInt(number), answer }))
  if (answerList.length === 0) return message.warning('请至少回答一道题')

  grading.value = true
  try {
    const data = await gradeExam({ exam_id: currentExamId.value, answers: answerList })
    gradeResult.value = data
    message.success('批改完成')
    loadRecords()
  } catch (e: any) { message.error(e.message) }
  finally { grading.value = false }
}

async function loadRecords() {
  recordsLoading.value = true
  try {
    const data = await listExamRecords(selectedKbId.value)
    records.value = data.items
  } catch {}
  finally { recordsLoading.value = false }
}

async function handleLoadRecord(id: number) {
  try {
    const data = await getExamRecord(id)
    currentExamId.value = data.id
    questions.value = data.questions
    examType.value = data.question_type
    answers.value = {}
    if (data.status === 'graded') {
      gradeResult.value = {
        total_score: data.total_score!,
        max_score: data.max_score!,
        summary: (data.total_score || 0) >= 90 ? '优秀！' : (data.total_score || 0) >= 60 ? '良好' : '需要加强',
        details: data.scores,
        dimensions: data.dimensions,
      }
    } else {
      gradeResult.value = null
    }
  } catch (e: any) { message.error(e.message) }
}

const typeMap: Record<string, string> = { choice: '选择题', essay: '简答题', tf: '判断题', mixed: '混合' }
const statusMap: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '待作答' },
  answered: { color: 'processing', text: '待批改' },
  graded: { color: 'success', text: '已批改' },
}

onMounted(() => { loadKBs(); loadRecords() })
</script>

<template>
  <div>
    <h2 style="margin-bottom: 24px"><EditOutlined /> 智能题库</h2>

    <a-row :gutter="16">
      <!-- 左栏 -->
      <a-col :span="8">
        <a-card title="🎯 生成题目" size="small">
          <a-form layout="vertical" size="small">
            <a-form-item label="知识库" required>
              <a-select v-model:value="selectedKbId" placeholder="请选择知识库">
                <a-select-option v-for="kb in kbList" :key="kb.id" :value="kb.id">{{ kb.name }}</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="题型">
              <a-select v-model:value="questionType">
                <a-select-option value="choice">选择题</a-select-option>
                <a-select-option value="essay">简答题</a-select-option>
                <a-select-option value="tf">判断题</a-select-option>
                <a-select-option value="mixed">混合题型</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item :label="`题目数量: ${questionCount}`">
              <a-slider v-model:value="questionCount" :min="1" :max="20" />
            </a-form-item>
            <a-form-item label="难度">
              <a-select v-model:value="difficulty">
                <a-select-option value="easy">简单</a-select-option>
                <a-select-option value="medium">中等</a-select-option>
                <a-select-option value="hard">困难</a-select-option>
              </a-select>
            </a-form-item>
            <a-button type="primary" block :loading="generating" @click="handleGenerate">
              <ThunderboltOutlined /> 生成题目
            </a-button>
          </a-form>
        </a-card>

        <a-card title="📋 考试记录" size="small" style="margin-top: 16px">
          <template #extra><a-button size="small" @click="loadRecords"><ReloadOutlined /></a-button></template>
          <a-list :loading="recordsLoading" :data-source="records" size="small">
            <template #renderItem="{ item }">
              <a-list-item style="cursor: pointer; padding: 8px 12px" @click="handleLoadRecord(item.id)">
                <a-list-item-meta>
                  <template #title>Exam #{{ item.id }} <a-tag :color="statusMap[item.status]?.color" size="small">{{ statusMap[item.status]?.text }}</a-tag></template>
                  <template #description>{{ item.question_count }}题 · {{ item.total_score || '-' }}/{{ item.max_score }}分 · {{ new Date(item.created_at).toLocaleString('zh-CN') }}</template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </a-col>

      <!-- 右栏 -->
      <a-col :span="16">
        <template v-if="questions.length">
          <!-- 题目区 -->
          <a-card :title="`📝 Exam #${currentExamId}`" size="small" style="margin-bottom: 16px">
            <template #extra><a-tag color="blue">{{ typeMap[examType] || examType }}</a-tag></template>
            <div v-for="q in questions" :key="q.number" style="border: 1px solid #f0f0f0; border-radius: 8px; padding: 12px; margin-bottom: 12px">
              <p><strong>第{{ q.number }}题</strong> <a-tag>{{ typeMap[q.type] || q.type }}</a-tag></p>
              <p>{{ q.stem }}</p>
              <ul v-if="q.options && q.options.length" style="list-style: none; padding: 0">
                <li v-for="o in q.options" :key="o" style="padding: 4px 0">{{ o }}</li>
              </ul>
              <a-collapse ghost>
                <a-collapse-panel key="1" header="参考答案">
                  <p style="color: #52c41a">{{ q.answer }}</p>
                </a-collapse-panel>
              </a-collapse>
            </div>
          </a-card>

          <!-- 作答区 -->
          <a-card title="✍️ 作答" size="small" style="margin-bottom: 16px">
            <div v-for="q in questions" :key="'a' + q.number" style="margin-bottom: 12px">
              <p><strong>第{{ q.number }}题</strong></p>
              <a-select
                v-if="q.type === 'choice'"
                v-model:value="answers[q.number]"
                :placeholder="'请选择答案'"
                style="width: 100%"
              >
                <a-select-option v-for="(o, i) in (q.options || [])" :key="i" :value="String.fromCharCode(65 + i)">{{ o }}</a-select-option>
              </a-select>
              <a-select
                v-else-if="q.type === 'tf'"
                v-model:value="answers[q.number]"
                placeholder="请选择"
                style="width: 100%"
              >
                <a-select-option value="正确">正确</a-select-option>
                <a-select-option value="错误">错误</a-select-option>
              </a-select>
              <a-textarea
                v-else
                v-model:value="answers[q.number]"
                :rows="3"
                placeholder="请输入你的答案..."
              />
            </div>
            <a-button type="primary" block :loading="grading" @click="handleGrade" :disabled="!currentExamId">
              <CheckOutlined /> 提交批改
            </a-button>
          </a-card>

          <!-- 批改结果 -->
          <a-card v-if="gradeResult" size="small">
            <template #title>📊 批改结果</template>
            <div style="text-align: center; margin-bottom: 16px">
              <a-progress
                type="circle"
                :percent="Math.round((gradeResult.total_score / gradeResult.max_score) * 100)"
                :stroke-color="gradeResult.total_score >= 90 ? '#52c41a' : gradeResult.total_score >= 60 ? '#faad14' : '#ff4d4f'"
                :format="() => `${gradeResult!.total_score}/${gradeResult!.max_score}`"
              />
              <p style="margin-top: 8px; font-size: 16px">{{ gradeResult.summary }}</p>
            </div>
            <a-divider />
            <div v-for="d in gradeResult.details" :key="d.question_number" style="padding: 8px; border: 1px solid #f0f0f0; border-radius: 4px; margin-bottom: 8px">
              <p><strong>第{{ d.question_number }}题</strong> <a-tag :color="d.is_correct ? 'success' : 'warning'">{{ d.score }} / {{ d.max_score }} 分</a-tag></p>
              <p style="color: #666; margin: 0">{{ d.comment }}</p>
            </div>
          </a-card>
        </template>

        <a-empty v-else description="选择知识库并点击「生成题目」开始" />
      </a-col>
    </a-row>
  </div>
</template>
