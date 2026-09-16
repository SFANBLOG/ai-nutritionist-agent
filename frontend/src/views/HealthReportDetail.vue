<template>
  <div v-loading="loading">
    <div class="flex justify-between items-center mb-6">
      <div class="flex items-center gap-3">
        <el-button :icon="ArrowLeft" circle @click="$router.push('/health-reports')" />
        <div>
          <h2 class="text-2xl font-bold text-gray-800 m-0">{{ report.report_name || '报告详情' }}</h2>
          <p class="text-gray-500 text-sm mt-1 mb-0">
            上传于 {{ formatDate(report.created_at, true) }}
          </p>
        </div>
      </div>
      <el-button type="success" :loading="generating" :icon="MagicStick" @click="handleGenerate">
        AI 生成个性化食谱
      </el-button>
    </div>

    <!-- 分析摘要 -->
    <el-alert
      v-if="analysis.summary"
      class="mb-6"
      :type="analysis.abnormal_count ? 'warning' : 'success'"
      :closable="false"
      show-icon
      :title="`AI 分析摘要(共 ${analysis.abnormal_count ?? 0} 项指标需要关注)`"
      :description="analysis.summary"
    />

    <el-row :gutter="20">
      <el-col :span="16">
        <el-card class="mb-5">
          <template #header>
            <span class="font-bold">健康指标明细</span>
          </template>
          <el-table :data="indicators" stripe>
            <el-table-column prop="name" label="指标" width="110" />
            <el-table-column label="数值" width="150">
              <template #default="{ row }">
                <span class="font-medium">{{ row.value }}</span>
                <span class="text-gray-400 text-xs ml-1">{{ row.unit }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="reference" label="参考范围" width="160" />
            <el-table-column label="评估" width="170">
              <template #default="{ row }">
                <el-tag :type="levelToTagType(row.level)" size="small">{{ row.level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="advice" label="饮食建议" min-width="220" />
            <template #empty>
              <el-empty description="未能识别标准指标" :image-size="80" />
            </template>
          </el-table>
        </el-card>

        <el-card>
          <template #header>
            <span class="font-bold">报告原文</span>
          </template>
          <div class="scroll-area text-sm text-gray-700">{{ report.report_content || '无内容' }}</div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="mb-5">
          <template #header>
            <span class="font-bold">关键指标</span>
          </template>
          <div class="space-y-3">
            <div
              v-for="item in metricCards"
              :key="item.label"
              class="flex items-center justify-between p-3 rounded-lg bg-gray-50"
            >
              <span class="text-sm text-gray-600">{{ item.label }}</span>
              <el-tag :type="item.type" effect="plain">
                {{ item.value ?? '未检测' }}
              </el-tag>
            </div>
          </div>
        </el-card>

        <el-card v-if="riskTags.length">
          <template #header>
            <span class="font-bold">风险提示</span>
          </template>
          <el-tag
            v-for="tag in riskTags"
            :key="tag"
            type="danger"
            effect="light"
            class="mr-2 mb-2"
          >
            {{ tag }}
          </el-tag>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, MagicStick } from '@element-plus/icons-vue'
import api from '@/api'
import { bloodPressureTagType, formatDate, glucoseTagType, levelToTagType } from '@/utils'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const generating = ref(false)
const report = ref({})

const analysis = computed(() => report.value.analysis_result || {})
const indicators = computed(() => analysis.value.indicators || [])
const riskTags = computed(() => analysis.value.risk_tags || [])

const metricCards = computed(() => [
  {
    label: '空腹血糖',
    value: report.value.blood_glucose,
    type: glucoseTagType(report.value.blood_glucose)
  },
  {
    label: '血压',
    value:
      report.value.blood_pressure_systolic
        ? `${report.value.blood_pressure_systolic}/${report.value.blood_pressure_diastolic}`
        : null,
    type: bloodPressureTagType(
      report.value.blood_pressure_systolic,
      report.value.blood_pressure_diastolic
    )
  },
  { label: '尿酸', value: report.value.uric_acid, type: 'info' },
  { label: '总胆固醇', value: report.value.cholesterol, type: 'info' },
  { label: '甘油三酯', value: report.value.triglycerides, type: 'info' }
])

const fetchReport = async () => {
  loading.value = true
  try {
    report.value = await api.healthReports.get(route.params.id)
  } catch {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

const handleGenerate = async () => {
  generating.value = true
  try {
    ElMessage.info('AI 营养师正在分析并生成食谱,请稍候…')
    const recipe = await api.recipes.generate({
      health_report_id: Number(route.params.id),
      days: 1
    })
    ElMessage.success('食谱生成成功')
    router.push(`/recipes/${recipe.id}`)
  } catch {
    /* 拦截器已提示 */
  } finally {
    generating.value = false
  }
}

onMounted(fetchReport)
</script>
