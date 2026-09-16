<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <div>
        <h2 class="text-2xl font-bold text-gray-800 m-0">我的食谱</h2>
        <p class="text-gray-500 text-sm mt-1 mb-0">
          由 AI 营养师基于您的体检指标与口味偏好生成(支持多日菜单与人工确认闸门)
        </p>
      </div>
      <el-button type="primary" :icon="MagicStick" @click="openGenerate">AI 生成食谱</el-button>
    </div>

    <el-row :gutter="20" v-loading="loading">
      <el-col v-for="recipe in recipes" :key="recipe.id" :span="8" class="mb-5">
        <el-card shadow="hover" class="h-full flex flex-col">
          <template #header>
            <div class="flex justify-between items-center gap-2">
              <span class="font-bold truncate">{{ recipe.name }}</span>
              <el-tag :type="statusType(recipe)" size="small">
                {{ statusLabel(recipe) }}
              </el-tag>
            </div>
          </template>

          <p class="text-gray-600 text-sm mb-4 line-clamp-3 min-h-[60px]">
            {{ recipe.description || '暂无描述' }}
          </p>

          <div class="grid grid-cols-3 gap-2 text-center mb-4">
            <div class="bg-orange-50 rounded p-2">
              <div class="text-orange-600 font-bold">{{ recipe.total_calories }}</div>
              <div class="text-xs text-gray-500">kcal(累计)</div>
            </div>
            <div class="bg-blue-50 rounded p-2">
              <div class="text-blue-600 font-bold">{{ recipe.cycle_label || (recipe.days + ' 天') }}</div>
              <div class="text-xs text-gray-500">方案周期</div>
            </div>
            <div class="bg-emerald-50 rounded p-2">
              <div class="text-emerald-600 font-bold">{{ (recipe.menus || []).length }}</div>
              <div class="text-xs text-gray-500">已生成日</div>
            </div>
          </div>

          <div class="flex justify-between items-center text-xs text-gray-400 mb-4">
            <span>{{ formatDate(recipe.created_at, true) }}</span>
            <el-tag
              v-if="recipe.nutrition_info?.review"
              :type="recipe.nutrition_info.review.passed ? 'success' : 'warning'"
              size="small"
              effect="plain"
            >
              {{ recipe.nutrition_info.review.passed ? '审核通过' : '待优化' }}
            </el-tag>
          </div>

          <!-- 人工确认闸门:待确认状态显示操作 -->
          <div v-if="recipe.status === 'pending_review'" class="flex gap-2 mb-3">
            <el-button type="success" size="small" class="flex-1" :loading="actingId === recipe.id && actingType === 'approve'" @click="handleApprove(recipe)">
              ✓ 确认采用
            </el-button>
            <el-button type="warning" size="small" class="flex-1" :loading="actingId === recipe.id && actingType === 'revise'" @click="handleRevise(recipe)">
              ↺ 请求修订
            </el-button>
          </div>
          <div v-else-if="recipe.status === 'revision_requested'" class="text-xs text-amber-600 mb-3">
            正在按意见重做…
          </div>
          <div v-else-if="recipe.revision_count" class="text-xs text-gray-400 mb-3">
            已修订 {{ recipe.revision_count }} 次 · 确认人 {{ recipe.reviewed_by }}
          </div>

          <div class="flex gap-2">
            <el-button type="primary" plain class="flex-1" @click="$router.push(`/recipes/${recipe.id}`)">
              查看详情
            </el-button>
            <el-button type="danger" plain @click="handleDelete(recipe)">删除</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="!loading && !recipes.length" description="暂无食谱">
      <el-button type="primary" @click="openGenerate">生成第一个食谱</el-button>
    </el-empty>

    <!-- 生成对话框 -->
    <el-dialog v-model="showGenerateDialog" title="AI 生成个性化食谱" width="520px">
      <el-alert
        v-if="!reports.length"
        class="mb-4"
        type="warning"
        :closable="false"
        show-icon
        title="请先上传体检报告"
        description="AI 需要基于体检指标才能生成个性化营养食谱"
      />
      <el-form :model="generateForm" label-width="110px">
        <el-form-item label="选择健康报告" required>
          <el-select
            v-model="generateForm.health_report_id"
            placeholder="请选择健康报告"
            class="w-full"
            :disabled="!reports.length"
          >
            <el-option
              v-for="r in reports"
              :key="r.id"
              :label="`${r.report_name}（${formatDate(r.created_at)}）`"
              :value="r.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="方案周期" required>
          <el-radio-group v-model="generateForm.period" class="w-full">
            <el-radio-button value="week">一周（7 天）</el-radio-button>
            <el-radio-button value="month">一个月（30 天）</el-radio-button>
            <el-radio-button value="custom">自定义</el-radio-button>
          </el-radio-group>
          <el-input-number
            v-if="generateForm.period === 'custom'"
            v-model="generateForm.days"
            :min="1"
            :max="90"
            class="mt-2"
            controls-position="right"
          />
        </el-form-item>
        <el-form-item label="起始日期">
          <el-date-picker
            v-model="generateForm.start_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="默认今天"
            class="w-full"
          />
        </el-form-item>
      </el-form>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="Agent 工作流将依次执行"
        :description="humanGate ? '健康分析 → 营养规划 → 食谱生成 → 质量审核,生成后进入「待人工确认」,需您确认采用或请求修订。' : '健康分析 → 营养规划 → 食谱生成 → 质量审核(不合格自动重做,最多 3 轮)'"
      />
      <template #footer>
        <el-button @click="showGenerateDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="generating"
          :disabled="!reports.length"
          @click="handleGenerate"
        >
          开始生成
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import api from '@/api'
import { formatDate } from '@/utils'

const router = useRouter()
const loading = ref(false)
const generating = ref(false)
const recipes = ref([])
const reports = ref([])
const showGenerateDialog = ref(false)

// HITL 闸门操作状态
const actingId = ref(null)
const actingType = ref('')

const generateForm = reactive({
  health_report_id: null,
  period: 'week',
  days: 7,
  start_date: ''
})

const mealsCount = (recipe) => (recipe.nutrition_info?.meals || []).length

const statusType = (recipe) => {
  if (recipe.status === 'pending_review') return 'warning'
  if (recipe.status === 'revision_requested') return 'info'
  if (recipe.status === 'active') return 'success'
  return 'info'
}
const statusLabel = (recipe) => {
  if (recipe.status === 'pending_review') return '待人工确认'
  if (recipe.status === 'revision_requested') return '重做中'
  if (recipe.status === 'active') return '已生效'
  return '已归档'
}

const humanGate = ref(true)

const fetchData = async () => {
  loading.value = true
  try {
    const [recipeList, reportList, health] = await Promise.all([
      api.recipes.list(),
      api.healthReports.list(),
      api.system.health().catch(() => ({}))
    ])
    recipes.value = recipeList
    reports.value = reportList
    humanGate.value = health?.human_review_gate !== false
  } catch {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

const openGenerate = () => {
  if (!reports.value.length) {
    ElMessage.warning('请先上传一份体检报告')
    return
  }
  generateForm.health_report_id = reports.value[0].id
  generateForm.period = 'week'
  generateForm.days = 7
  generateForm.start_date = ''
  showGenerateDialog.value = true
}

const handleGenerate = async () => {
  if (!generateForm.health_report_id) {
    ElMessage.warning('请选择健康报告')
    return
  }
  // 周期 -> 天数(week/month 由后端换算,前端仅用于提示文案)
  const periodDays =
    generateForm.period === 'week' ? 7
    : generateForm.period === 'month' ? 30
    : (generateForm.days || 7)
  const periodLabel =
    generateForm.period === 'week' ? '一周'
    : generateForm.period === 'month' ? '一个月'
    : `自定义 ${periodDays} 天`
  generating.value = true
  try {
    ElMessage.info(`AI 营养师正在生成${periodLabel}菜单,请稍候…`)
    const recipe = await api.recipes.generate({
      health_report_id: generateForm.health_report_id,
      period: generateForm.period,
      days: generateForm.days,
      start_date: generateForm.start_date || undefined
    })
    ElMessage.success(humanGate.value ? '多日菜单已生成,等待您确认采用' : '食谱生成成功')
    showGenerateDialog.value = false
    await fetchData()
    if (recipe?.id) {
      router.push(`/recipes/${recipe.id}`)
    }
  } catch {
    /* 拦截器已提示 */
  } finally {
    generating.value = false
  }
}

const handleApprove = async (recipe) => {
  actingId.value = recipe.id
  actingType.value = 'approve'
  try {
    await api.recipes.approveReview(recipe.id, { decision: '人工确认通过' })
    ElMessage.success('已确认采用,食谱生效')
    await fetchData()
  } catch {
    /* 拦截器已提示 */
  } finally {
    actingId.value = null
    actingType.value = ''
  }
}

const handleRevise = async (recipe) => {
  let notes
  try {
    const { value } = await ElMessageBox.prompt('请填写修订意见(将作为 AI 重做的指令)', '请求修订', {
      confirmButtonText: '提交修订',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputValidator: (v) => (v && v.trim() ? true : '修订意见不能为空')
    })
    notes = v
  } catch {
    return
  }
  actingId.value = recipe.id
  actingType.value = 'revise'
  try {
    await api.recipes.requestRevision(recipe.id, { notes })
    ElMessage.success('已按意见重做,请再次确认')
    await fetchData()
  } catch {
    /* 拦截器已提示 */
  } finally {
    actingId.value = null
    actingType.value = ''
  }
}

const handleDelete = async (recipe) => {
  try {
    await ElMessageBox.confirm(`确认删除食谱「${recipe.name}」吗?`, '删除确认', {
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    await api.recipes.remove(recipe.id)
    ElMessage.success('删除成功')
    await fetchData()
  } catch {
    /* 拦截器已提示 */
  }
}

onMounted(fetchData)
</script>
