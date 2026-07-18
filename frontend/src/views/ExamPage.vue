<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  EditOutlined,
  ThunderboltOutlined,
  CheckOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  SettingOutlined,
  HistoryOutlined,
  TrophyOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons-vue'
import { listKnowledgeBases } from '../api/knowledge'
import { generateExam, gradeExam, listExamRecords, getExamRecord } from '../api/exam'
import type { KnowledgeBase, QuestionItem, ExamRecord, GradeDetail, DimensionScore } from '../api/types'
import { message, Modal } from 'ant-design-vue'
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'

// === Radar Chart Helpers (exposed to template) ===
function getPolygonPoints(sides: number, radius: number, cx: number, cy: number): string {
  const pts: string[] = []
  for (let i = 0; i < sides; i++) {
    const angle = (Math.PI * 2 * i) / sides - Math.PI / 2
    pts.push(`${cx + radius * Math.cos(angle)},${cy + radius * Math.sin(angle)}`)
  }
  return pts.join(' ')
}
function getAxisEnd(index: number, sides: number, radius: number, cx: number, cy: number): { x: number; y: number } {
  const angle = (Math.PI * 2 * (index - 1)) / sides - Math.PI / 2
  return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) }
}
function getDataPoints(dims: { name: string; value: number; max: number }[], radius: number, cx: number, cy: number): string {
  const pts: string[] = []
  for (let i = 0; i < dims.length; i++) {
    const angle = (Math.PI * 2 * i) / dims.length - Math.PI / 2
    const r = (dims[i].value / dims[i].max) * radius
    pts.push(`${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`)
  }
  return pts.join(' ')
}

// === State ===
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
const showAnswers = ref(false)
const examMode = ref(false)
const timerSeconds = ref(0)
const timerRunning = ref(false)
let timerInterval: ReturnType<typeof setInterval> | null = null

const gradeResult = ref<{
  total_score: number; max_score: number; summary: string
  details: GradeDetail[]; dimensions?: DimensionScore | null
} | null>(null)

const records = ref<ExamRecord[]>([])
const recordsLoading = ref(false)

// === Methods ===
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
    showAnswers.value = false
    examMode.value = true
    startTimer()
    message.success(`成功生成 ${data.question_count} 道题目`)
  } catch (e: any) { message.error(e.message) }
  finally { generating.value = false }
}

function startTimer() {
  timerSeconds.value = 0
  timerRunning.value = true
  timerInterval = setInterval(() => { timerSeconds.value++ }, 1000)
}
function stopTimer() {
  timerRunning.value = false
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null }
}

const timerDisplay = computed(() => {
  const m = Math.floor(timerSeconds.value / 60).toString().padStart(2, '0')
  const s = (timerSeconds.value % 60).toString().padStart(2, '0')
  return `${m}:${s}`
})

// 已答题数
const answeredCount = computed(() => {
  return Object.values(answers.value).filter(v => v && v.trim()).length
})

function handleSubmit() {
  const answerList = Object.entries(answers.value)
    .filter(([, v]) => v.trim())
    .map(([number, answer]) => ({ number: parseInt(number), answer }))
  if (answerList.length === 0) return message.warning('请至少回答一道题')

  Modal.confirm({
    title: '确认交卷？',
    content: `你已作答 ${answerList.length}/${questions.value.length} 题，用时 ${timerDisplay.value}。提交后将无法修改。`,
    okText: '确认交卷',
    cancelText: '继续作答',
    onOk: () => handleGrade(),
  })
}

async function handleGrade() {
  if (!currentExamId.value) return
  stopTimer()
  examMode.value = false
  showAnswers.value = true
  const answerList = Object.entries(answers.value)
    .filter(([, v]) => v.trim())
    .map(([number, answer]) => ({ number: parseInt(number), answer }))

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
    stopTimer()
    examMode.value = false
    showAnswers.value = true
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

const difficultyMap: Record<string, { label: string; color: string }> = {
  easy: { label: '简单', color: '#52c41a' },
  medium: { label: '中等', color: '#faad14' },
  hard: { label: '困难', color: '#ff4d4f' },
}

// 判断某题是否答对（批改后）
function isQuestionCorrect(q: QuestionItem): boolean | null {
  if (!gradeResult.value) return null
  const detail = gradeResult.value.details.find(d => d.question_number === q.number)
  return detail ? detail.is_correct : null
}

// 获取选项字母
function getOptionLabel(i: number): string {
  return String.fromCharCode(65 + i)
}

const radarDimensions = computed(() => {
  if (!gradeResult.value?.dimensions) return null
  const d = gradeResult.value.dimensions
  return [
    { name: '概念理解', value: d.concept, max: 25 },
    { name: '分析能力', value: d.analysis, max: 25 },
    { name: '记忆准确', value: d.memory, max: 25 },
    { name: '应用能力', value: d.application, max: 25 },
  ]
})

onMounted(() => { loadKBs(); loadRecords() })
</script>

<template>
  <div class="exam-page">
    <PageHeader
      :icon="EditOutlined"
      title="智能题库"
      description="AI 自动出题、在线作答、四维度智能批改"
    />

    <a-row :gutter="[20, 20]" class="exam-layout">
      <!-- ========== 左侧：出题配置 + 考试记录 ========== -->
      <a-col :xs="24" :lg="7" :xl="6">
        <!-- 出题配置卡片 -->
        <a-card class="config-card" :body-style="{ padding: '20px' }">
          <template #title>
            <div class="card-title">
              <SettingOutlined class="card-title-icon" />
              <span>生成题目</span>
            </div>
          </template>

          <a-form layout="vertical" size="middle">
            <a-form-item label="知识库" required>
              <a-select v-model:value="selectedKbId" placeholder="请选择知识库">
                <a-select-option v-for="kb in kbList" :key="kb.id" :value="kb.id">{{ kb.name }}</a-select-option>
              </a-select>
            </a-form-item>

            <a-form-item label="题型">
              <a-radio-group v-model:value="questionType" button-style="solid" class="type-radio">
                <a-radio-button value="choice">选择</a-radio-button>
                <a-radio-button value="essay">简答</a-radio-button>
                <a-radio-button value="tf">判断</a-radio-button>
                <a-radio-button value="mixed">混合</a-radio-button>
              </a-radio-group>
            </a-form-item>

            <a-form-item :label="`题目数量 · ${questionCount} 题`">
              <a-slider v-model:value="questionCount" :min="1" :max="20" :marks="{ 1: '1', 5: '5', 10: '10', 20: '20' }" />
            </a-form-item>

            <a-form-item label="难度">
              <a-radio-group v-model:value="difficulty" button-style="solid" class="type-radio">
                <a-radio-button value="easy">
                  <span :style="{ color: difficulty === 'easy' ? '#fff' : difficultyMap.easy.color }">简单</span>
                </a-radio-button>
                <a-radio-button value="medium">
                  <span :style="{ color: difficulty === 'medium' ? '#fff' : difficultyMap.medium.color }">中等</span>
                </a-radio-button>
                <a-radio-button value="hard">
                  <span :style="{ color: difficulty === 'hard' ? '#fff' : difficultyMap.hard.color }">困难</span>
                </a-radio-button>
              </a-radio-group>
            </a-form-item>

            <a-button type="primary" block size="large" :loading="generating" @click="handleGenerate" class="generate-btn">
              <ThunderboltOutlined /> 生成题目
            </a-button>
          </a-form>
        </a-card>

        <!-- 考试记录卡片 -->
        <a-card class="records-card" :body-style="{ padding: '12px' }">
          <template #title>
            <div class="card-title">
              <HistoryOutlined class="card-title-icon" />
              <span>考试记录</span>
            </div>
          </template>
          <template #extra>
            <a-button type="text" size="small" @click="loadRecords"><ReloadOutlined /></a-button>
          </template>

          <a-spin :spinning="recordsLoading">
            <div v-if="records.length === 0 && !recordsLoading" class="records-empty">
              <p>暂无考试记录</p>
            </div>
            <div v-else class="record-list">
              <div
                v-for="(item, idx) in records"
                :key="item.id"
                class="record-item stagger-in"
                :style="{ '--i': idx }"
                @click="handleLoadRecord(item.id)"
              >
                <div class="record-main">
                  <div class="record-title">
                    <span class="record-id">Exam #{{ item.id }}</span>
                    <a-tag :color="statusMap[item.status]?.color" class="record-tag">{{ statusMap[item.status]?.text }}</a-tag>
                  </div>
                  <div class="record-meta">
                    <span>{{ item.question_count }}题</span>
                    <span v-if="item.total_score !== null && item.total_score !== undefined">
                      · {{ item.total_score }}/{{ item.max_score }}分
                    </span>
                  </div>
                  <div class="record-time">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</div>
                </div>
              </div>
            </div>
          </a-spin>
        </a-card>
      </a-col>

      <!-- ========== 右侧：题目展示 + 答题 + 批改 ========== -->
      <a-col :xs="24" :lg="17" :xl="18">
        <template v-if="questions.length">
          <!-- 计时器 + 进度条 -->
          <div v-if="examMode && timerRunning" class="exam-status-bar">
            <div class="status-left">
              <ClockCircleOutlined class="status-icon" />
              <span class="status-text">考试进行中</span>
              <span class="status-timer">{{ timerDisplay }}</span>
            </div>
            <div class="status-right">
              <span class="progress-text">{{ answeredCount }} / {{ questions.length }} 已答</span>
              <div class="mini-progress">
                <div class="mini-progress-bar" :style="{ width: (questions.length ? (answeredCount / questions.length * 100) : 0) + '%' }" />
              </div>
            </div>
          </div>

          <!-- 题目展示区 -->
          <a-card class="questions-card" :body-style="{ padding: '20px' }">
            <template #title>
              <div class="card-title">
                <FileTextOutlined class="card-title-icon" />
                <span>Exam #{{ currentExamId }}</span>
                <a-tag color="blue" class="title-tag">{{ typeMap[examType] || examType }}</a-tag>
              </div>
            </template>
            <template #extra>
              <a-button v-if="!examMode" type="text" size="small" @click="showAnswers = !showAnswers">
                <template #icon>
                  <EyeOutlined v-if="showAnswers" />
                  <EyeInvisibleOutlined v-else />
                </template>
                {{ showAnswers ? '隐藏答案' : '显示答案' }}
              </a-button>
            </template>

            <div class="question-list">
              <div
                v-for="(q, idx) in questions"
                :key="q.number"
                class="question-card stagger-in"
                :style="{ '--i': idx }"
                :class="{
                  'is-correct': isQuestionCorrect(q) === true,
                  'is-wrong': isQuestionCorrect(q) === false,
                }"
              >
                <!-- 题目头部 -->
                <div class="question-header">
                  <div class="question-num">
                    <span class="num-badge">{{ q.number }}</span>
                    <a-tag size="small" class="type-tag">{{ typeMap[q.type] || q.type }}</a-tag>
                  </div>
                  <CheckCircleOutlined v-if="isQuestionCorrect(q) === true" class="result-icon correct" />
                  <CloseCircleOutlined v-else-if="isQuestionCorrect(q) === false" class="result-icon wrong" />
                </div>

                <!-- 题干 -->
                <p class="question-stem">{{ q.stem }}</p>

                <!-- 选项展示（仅选择题） -->
                <ul v-if="q.options && q.options.length" class="option-list">
                  <li
                    v-for="(o, i) in q.options"
                    :key="i"
                    class="option-item"
                    :class="{
                      'option-selected': examMode && answers[q.number] === getOptionLabel(i),
                      'option-correct': !examMode && showAnswers && q.answer && q.answer.includes(getOptionLabel(i)),
                      'option-chosen-wrong': !examMode && showAnswers && answers[q.number] === getOptionLabel(i) && (!q.answer || !q.answer.includes(getOptionLabel(i))),
                    }"
                  >
                    <span class="option-label">{{ getOptionLabel(i) }}</span>
                    <span class="option-text">{{ o }}</span>
                  </li>
                </ul>

                <!-- 参考答案（非考试模式） -->
                <transition name="page">
                  <div v-if="!examMode && showAnswers" class="answer-block">
                    <div class="answer-label">
                      <CheckCircleOutlined /> 参考答案
                    </div>
                    <p class="answer-text">{{ q.answer }}</p>
                  </div>
                </transition>
              </div>
            </div>
          </a-card>

          <!-- 作答区 -->
          <a-card class="answer-card" :body-style="{ padding: '20px' }">
            <template #title>
              <div class="card-title">
                <EditOutlined class="card-title-icon" />
                <span>{{ examMode ? '作答区域' : '我的答案' }}</span>
              </div>
            </template>

            <div class="answer-list">
              <div v-for="q in questions" :key="'a' + q.number" class="answer-row">
                <div class="answer-row-header">
                  <span class="answer-num">第 {{ q.number }} 题</span>
                  <a-tag v-if="q.type" size="small">{{ typeMap[q.type] }}</a-tag>
                </div>

                <!-- 选择题：可点击选项 -->
                <div v-if="q.type === 'choice'" class="answer-options">
                  <div
                    v-for="(o, i) in (q.options || [])"
                    :key="i"
                    class="answer-option"
                    :class="{ 'selected': answers[q.number] === getOptionLabel(i) }"
                    @click="examMode && (!gradeResult) && (answers[q.number] = getOptionLabel(i))"
                  >
                    <span class="answer-option-label">{{ getOptionLabel(i) }}</span>
                    <span class="answer-option-text">{{ o }}</span>
                  </div>
                </div>

                <!-- 判断题：两个按钮 -->
                <div v-else-if="q.type === 'tf'" class="answer-tf">
                  <div
                    class="tf-btn"
                    :class="{ 'selected': answers[q.number] === '正确' }"
                    @click="examMode && (!gradeResult) && (answers[q.number] = '正确')"
                  >
                    <CheckCircleOutlined /> 正确
                  </div>
                  <div
                    class="tf-btn"
                    :class="{ 'selected': answers[q.number] === '错误' }"
                    @click="examMode && (!gradeResult) && (answers[q.number] = '错误')"
                  >
                    <CloseCircleOutlined /> 错误
                  </div>
                </div>

                <!-- 简答题：文本域 -->
                <a-textarea
                  v-else
                  v-model:value="answers[q.number]"
                  :rows="3"
                  placeholder="请输入你的答案..."
                  :disabled="!examMode && !!gradeResult"
                  class="answer-textarea"
                />
              </div>
            </div>

            <div class="answer-actions">
              <a-button
                v-if="examMode"
                type="primary"
                size="large"
                block
                :loading="grading"
                @click="handleSubmit"
              >
                <CheckOutlined /> 提交交卷
              </a-button>
              <a-button
                v-else-if="!gradeResult"
                type="primary"
                size="large"
                block
                :loading="grading"
                @click="handleGrade"
              >
                <CheckOutlined /> 提交批改
              </a-button>
            </div>
          </a-card>

          <!-- 批改结果 -->
          <transition name="page">
            <a-card v-if="gradeResult" class="grade-card" :body-style="{ padding: '24px' }">
              <template #title>
                <div class="card-title">
                  <TrophyOutlined class="card-title-icon" />
                  <span>批改结果</span>
                </div>
              </template>

              <!-- 评分总览 -->
              <a-row :gutter="24" class="grade-overview">
                <a-col :xs="24" :sm="gradeResult.dimensions ? 12 : 24">
                  <div class="score-center">
                    <a-progress
                      type="circle"
                      :percent="Math.round((gradeResult.total_score / gradeResult.max_score) * 100)"
                      :stroke-color="gradeResult.total_score >= 90 ? '#52c41a' : gradeResult.total_score >= 60 ? '#faad14' : '#ff4d4f'"
                      :format="() => `${gradeResult!.total_score}`"
                      :width="160"
                      :stroke-width="8"
                    />
                    <div class="score-meta">
                      <span class="score-total">/ {{ gradeResult.max_score }} 分</span>
                    </div>
                    <p class="score-summary">{{ gradeResult.summary }}</p>
                  </div>
                </a-col>

                <!-- 雷达图 -->
                <a-col v-if="radarDimensions" :xs="24" :sm="12">
                  <div class="radar-chart">
                    <svg viewBox="0 0 200 200" class="radar-svg">
                      <g v-for="i in 5" :key="i">
                        <polygon
                          :points="getPolygonPoints(4, (i / 5) * 80, 100, 100)"
                          fill="none"
                          stroke="var(--border-color)"
                          stroke-width="0.5"
                        />
                      </g>
                      <line
                        v-for="i in 4"
                        :key="'axis-' + i"
                        :x1="100" :y1="100"
                        :x2="getAxisEnd(i, 4, 80, 100, 100).x"
                        :y2="getAxisEnd(i, 4, 80, 100, 100).y"
                        stroke="var(--border-color)"
                        stroke-width="0.5"
                      />
                      <text
                        v-for="(dim, i) in radarDimensions"
                        :key="'label-' + i"
                        :x="getAxisEnd(i + 1, 4, 92, 100, 100).x"
                        :y="getAxisEnd(i + 1, 4, 92, 100, 100).y"
                        text-anchor="middle"
                        dominant-baseline="middle"
                        font-size="9"
                        fill="var(--text-secondary)"
                      >
                        {{ dim.name }}
                      </text>
                      <polygon
                        :points="getDataPoints(radarDimensions, 80, 100, 100)"
                        fill="rgba(22, 119, 255, 0.2)"
                        stroke="var(--color-primary)"
                        stroke-width="1.5"
                      />
                      <circle
                        v-for="(dim, i) in radarDimensions"
                        :key="'point-' + i"
                        :cx="getAxisEnd(i + 1, 4, (dim.value / dim.max) * 80, 100, 100).x"
                        :cy="getAxisEnd(i + 1, 4, (dim.value / dim.max) * 80, 100, 100).y"
                        r="3"
                        fill="var(--color-primary)"
                      />
                    </svg>
                    <div class="radar-legend">
                      <div v-for="(dim, i) in radarDimensions" :key="i" class="legend-item">
                        <span class="legend-name">{{ dim.name }}</span>
                        <span class="legend-value">{{ dim.value }}/{{ dim.max }}</span>
                      </div>
                    </div>
                  </div>
                </a-col>
              </a-row>

              <a-divider />

              <!-- 逐题反馈 -->
              <div class="detail-list">
                <div
                  v-for="(d, idx) in gradeResult.details"
                  :key="d.question_number"
                  class="grade-detail stagger-in"
                  :style="{ '--i': idx }"
                  :class="{ 'detail-correct': d.is_correct, 'detail-wrong': !d.is_correct }"
                >
                  <div class="detail-header">
                    <div class="detail-title">
                      <CheckCircleOutlined v-if="d.is_correct" class="detail-icon correct" />
                      <CloseCircleOutlined v-else class="detail-icon wrong" />
                      <strong>第 {{ d.question_number }} 题</strong>
                    </div>
                    <div class="detail-score" :class="{ 'score-full': d.score === d.max_score }">
                      {{ d.score }} / {{ d.max_score }} 分
                    </div>
                  </div>
                  <p class="detail-comment">{{ d.comment }}</p>
                </div>
              </div>
            </a-card>
          </transition>
        </template>

        <!-- 空状态 -->
        <EmptyState
          v-else
          type="bolt"
          title="开始生成题目"
          description="在左侧选择知识库和题型，点击「生成题目」开始练习"
        />
      </a-col>
    </a-row>
  </div>
</template>

<style scoped>
.exam-page {
  animation: fade-in var(--duration-normal) var(--ease-premium);
}

/* === 卡片标题统一 === */
.card-title {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-weight: var(--font-weight-semibold);
  font-size: var(--font-size-lg);
}
.card-title-icon {
  color: var(--color-primary);
  font-size: 18px;
}
.title-tag {
  margin-left: var(--space-xs);
}

/* === 配置卡片 === */
.config-card {
  border-radius: var(--border-radius-lg);
  margin-bottom: var(--space-md);
}
.type-radio {
  display: flex;
  width: 100%;
}
.type-radio :deep(.ant-radio-button-wrapper) {
  flex: 1;
  text-align: center;
}
.generate-btn {
  margin-top: var(--space-sm);
  height: var(--btn-height-lg);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
}

/* === 记录卡片 === */
.records-card {
  border-radius: var(--border-radius-lg);
}
.records-empty {
  text-align: center;
  padding: var(--space-lg);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}
.record-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}
.record-item {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--border-radius-md);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-premium);
  border: 1px solid transparent;
}
.record-item:hover {
  background: var(--bg-hover);
  border-color: var(--border-color);
  transform: translateX(2px);
}
.record-title {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
}
.record-id {
  font-weight: var(--font-weight-medium);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.record-tag {
  font-size: var(--font-size-xs);
}
.record-meta {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
}
.record-time {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
}

/* === 考试状态条 === */
.exam-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-active);
  border: 1px solid rgba(22, 119, 255, 0.2);
  border-radius: var(--border-radius-lg);
  margin-bottom: var(--space-md);
  flex-wrap: wrap;
  gap: var(--space-sm);
}
.status-left {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
.status-icon {
  color: var(--color-primary);
  font-size: 18px;
}
.status-text {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.status-timer {
  font-family: var(--font-family-mono);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
}
.status-right {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
.progress-text {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  white-space: nowrap;
}
.mini-progress {
  width: 100px;
  height: 6px;
  background: var(--bg-hover);
  border-radius: var(--border-radius-full);
  overflow: hidden;
}
.mini-progress-bar {
  height: 100%;
  background: var(--gradient-primary);
  border-radius: var(--border-radius-full);
  transition: width var(--duration-normal) var(--ease-premium);
}

/* === 题目卡片 === */
.questions-card {
  border-radius: var(--border-radius-lg);
  margin-bottom: var(--space-md);
}
.question-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}
.question-card {
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-lg);
  padding: var(--space-md);
  background: var(--bg-card);
  transition: all var(--duration-normal) var(--ease-premium);
}
.question-card:hover {
  border-color: var(--color-primary-light);
  box-shadow: var(--shadow-sm);
}
.question-card.is-correct {
  border-color: var(--color-success);
  background: rgba(82, 196, 26, 0.04);
}
.question-card.is-wrong {
  border-color: var(--color-error);
  background: rgba(255, 77, 79, 0.04);
}
.question-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-sm);
}
.question-num {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
.num-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--border-radius-md);
  background: var(--gradient-primary);
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.type-tag {
  font-size: var(--font-size-xs);
}
.result-icon {
  font-size: 20px;
}
.result-icon.correct {
  color: var(--color-success);
}
.result-icon.wrong {
  color: var(--color-error);
}
.question-stem {
  margin: 0 0 var(--space-sm);
  color: var(--text-primary);
  font-size: var(--font-size-md);
  line-height: var(--line-height-relaxed);
}

/* 选项展示 */
.option-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}
.option-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--border-radius-md);
  background: var(--bg-hover);
  transition: all var(--duration-fast) ease;
  font-size: var(--font-size-sm);
}
.option-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: var(--border-radius-sm);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-weight: var(--font-weight-medium);
  font-size: var(--font-size-xs);
  flex-shrink: 0;
}
.option-text {
  color: var(--text-secondary);
}
.option-item.option-correct {
  background: rgba(82, 196, 26, 0.1);
}
.option-item.option-correct .option-label {
  background: var(--color-success);
  color: #fff;
}
.option-item.option-correct .option-text {
  color: var(--color-success);
  font-weight: var(--font-weight-medium);
}
.option-item.option-chosen-wrong {
  background: rgba(255, 77, 79, 0.1);
}
.option-item.option-chosen-wrong .option-label {
  background: var(--color-error);
  color: #fff;
}
.option-item.option-selected {
  background: var(--bg-active);
  border: 1px solid var(--color-primary);
}

/* 参考答案块 */
.answer-block {
  margin-top: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  background: rgba(82, 196, 26, 0.06);
  border-left: 3px solid var(--color-success);
  border-radius: 0 var(--border-radius-md) var(--border-radius-md) 0;
}
.answer-label {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-success);
  margin-bottom: var(--space-xs);
}
.answer-text {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
}

/* === 作答区 === */
.answer-card {
  border-radius: var(--border-radius-lg);
  margin-bottom: var(--space-md);
}
.answer-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}
.answer-row-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
}
.answer-num {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
}

/* 选择题作答选项 */
.answer-options {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}
.answer-option {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-premium);
  background: var(--bg-card);
}
.answer-option:hover {
  border-color: var(--color-primary-light);
  background: var(--bg-hover);
}
.answer-option.selected {
  border-color: var(--color-primary);
  background: var(--bg-active);
  box-shadow: 0 0 0 1px var(--color-primary);
}
.answer-option-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--border-radius-sm);
  background: var(--bg-hover);
  color: var(--text-secondary);
  font-weight: var(--font-weight-medium);
  font-size: var(--font-size-sm);
  flex-shrink: 0;
  transition: all var(--duration-fast) ease;
}
.answer-option.selected .answer-option-label {
  background: var(--color-primary);
  color: #fff;
}
.answer-option-text {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
}

/* 判断题按钮 */
.answer-tf {
  display: flex;
  gap: var(--space-sm);
}
.tf-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: var(--space-md);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  cursor: pointer;
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  transition: all var(--duration-fast) var(--ease-premium);
  background: var(--bg-card);
}
.tf-btn:hover {
  border-color: var(--color-primary-light);
  background: var(--bg-hover);
}
.tf-btn.selected {
  border-color: var(--color-primary);
  background: var(--bg-active);
  color: var(--color-primary);
  box-shadow: 0 0 0 1px var(--color-primary);
}
.answer-textarea {
  border-radius: var(--border-radius-md);
}
.answer-actions {
  margin-top: var(--space-md);
}
.answer-actions :deep(.ant-btn) {
  height: var(--btn-height-lg);
  font-size: var(--font-size-md);
}

/* === 批改结果 === */
.grade-card {
  border-radius: var(--border-radius-lg);
}
.grade-overview {
  margin-bottom: var(--space-md);
}
.score-center {
  text-align: center;
  padding: var(--space-md) 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.score-meta {
  margin-top: var(--space-sm);
}
.score-total {
  font-size: var(--font-size-lg);
  color: var(--text-tertiary);
  font-weight: var(--font-weight-medium);
}
.score-summary {
  margin-top: var(--space-sm);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

/* 雷达图 */
.radar-chart {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-sm);
}
.radar-svg {
  width: 180px;
  height: 180px;
}
.radar-legend {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-xs) var(--space-md);
  margin-top: var(--space-sm);
  width: 100%;
}
.legend-item {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-xs);
}
.legend-name {
  color: var(--text-secondary);
}
.legend-value {
  color: var(--color-primary);
  font-weight: var(--font-weight-medium);
  font-family: var(--font-family-mono);
}

/* 逐题反馈 */
.detail-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}
.grade-detail {
  padding: var(--space-md);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  background: var(--bg-card);
  transition: all var(--duration-fast) ease;
}
.grade-detail.detail-correct {
  border-left: 3px solid var(--color-success);
}
.grade-detail.detail-wrong {
  border-left: 3px solid var(--color-error);
}
.grade-detail:hover {
  box-shadow: var(--shadow-sm);
}
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-sm);
}
.detail-title {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.detail-icon {
  font-size: 16px;
}
.detail-icon.correct {
  color: var(--color-success);
}
.detail-icon.wrong {
  color: var(--color-error);
}
.detail-score {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
  font-family: var(--font-family-mono);
}
.detail-score.score-full {
  color: var(--color-success);
}
.detail-comment {
  color: var(--text-secondary);
  margin: 0;
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
}
</style>
