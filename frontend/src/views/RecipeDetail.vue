<template>
  <div v-loading="loading">
    <div class="flex justify-between items-center mb-6">
      <div class="flex items-center gap-3">
        <el-button :icon="ArrowLeft" circle @click="$router.push('/recipes')" />
        <div>
          <h2 class="text-2xl font-bold text-gray-800 m-0">{{ recipe.name || '食谱详情' }}</h2>
          <p class="text-gray-500 text-sm mt-1 mb-0">
            生成于 {{ formatDate(recipe.created_at, true) }}
            <span v-if="nutrition.llm_enabled" class="ml-2 text-emerald-600">· LLM 增强生成</span>
            <span v-else class="ml-2 text-gray-400">· 规则引擎生成</span>
            <el-tag class="ml-2" :type="statusType" size="small">{{ statusLabel }}</el-tag>
          </p>
        </div>
      </div>
      <el-button :icon="Printer" @click="handlePrint">打印 / 导出 PDF</el-button>
    </div>

    <!-- 按天切换 -->
    <el-row :gutter="16" class="mb-5" v-if="menus.length">
      <el-col :span="24">
        <el-card shadow="never">
          <div class="flex items-center justify-between flex-wrap gap-3">
            <el-radio-group v-model="selectedDay" size="small">
              <el-radio-button v-for="(m, i) in menus" :key="m.id" :value="i">
                {{ formatDay(m.menu_date) }}
              </el-radio-button>
            </el-radio-group>
            <span class="text-sm text-gray-500">
              周期 {{ recipe.cycle_label || (recipe.days + ' 天') }} · 共 {{ recipe.days }} 天 · 起始 {{ recipe.start_date || menus[0]?.menu_date }}
            </span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mb-5" v-if="currentMenu">
      <el-col :span="24">
        <el-card shadow="never">
          <div class="grid grid-cols-4 gap-3 text-center">
            <div class="bg-orange-50 rounded p-2">
              <div class="text-orange-600 font-bold">{{ currentMenu.total_calories }}</div>
              <div class="text-xs text-gray-500">当日热量 kcal</div>
            </div>
            <div class="bg-blue-50 rounded p-2">
              <div class="text-blue-600 font-bold">{{ currentMenu.total_protein }}</div>
              <div class="text-xs text-gray-500">蛋白质 g</div>
            </div>
            <div class="bg-purple-50 rounded p-2">
              <div class="text-purple-600 font-bold">{{ currentMenu.total_carbohydrate }}</div>
              <div class="text-xs text-gray-500">碳水 g</div>
            </div>
            <div class="bg-red-50 rounded p-2">
              <div class="text-red-400 font-bold">{{ currentMenu.total_fat }}</div>
              <div class="text-xs text-gray-500">脂肪 g</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="16">
        <!-- 方案说明 -->
        <el-card class="mb-5">
          <template #header>
            <span class="font-bold">方案说明</span>
          </template>
          <p class="text-gray-700 leading-7 m-0">{{ recipe.description || '暂无描述' }}</p>
        </el-card>

        <!-- 当日餐单 -->
        <el-card class="mb-5" v-if="currentMenu">
          <template #header>
            <div class="flex justify-between items-center">
              <span class="font-bold">{{ formatDay(currentMenu.menu_date) }} 餐单</span>
              <el-tag v-if="dayReview.passed" type="success" size="small">
                当日审核通过
              </el-tag>
              <el-tag v-else-if="dayReview.issues?.length" type="warning" size="small">
                当日待优化
              </el-tag>
            </div>
          </template>

          <div v-for="meal in currentMenu.meals" :key="meal.id" class="mb-6 last:mb-0">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2">
                <span class="text-lg">{{ mealIcon(meal.meal_type) }}</span>
                <span class="font-semibold text-gray-800">{{ mealLabel(meal.meal_type) }}</span>
              </div>
              <span class="text-sm text-gray-500">
                目标 {{ meal.target_calories }} kcal / 实际 {{ meal.actual_calories }} kcal
              </span>
            </div>

            <el-row :gutter="12">
              <el-col v-for="dish in meal.dishes" :key="dish.id" :span="12" class="mb-3">
                <div class="border border-gray-200 rounded-lg p-3 h-full hover:border-emerald-300 transition">
                  <div class="flex justify-between items-start mb-2">
                    <span class="font-medium text-gray-800">{{ dish.name }}</span>
                    <el-tag size="small" type="warning" effect="plain">{{ dish.calories }} kcal</el-tag>
                  </div>
                  <div class="text-xs text-gray-500 space-y-1">
                    <div><span class="text-gray-400">食材:</span>{{ dish.ingredients || '-' }}</div>
                    <div><span class="text-gray-400">做法:</span>{{ dish.cooking_method || '-' }}</div>
                    <div class="flex gap-3 pt-1">
                      <span>蛋白 {{ dish.protein }}g</span>
                      <span>碳水 {{ dish.carbohydrate }}g</span>
                      <span>脂肪 {{ dish.fat }}g</span>
                      <span>纤维 {{ dish.fiber }}g</span>
                    </div>
                    <el-alert
                      v-if="dish.tips"
                      class="mt-2"
                      type="success"
                      :closable="false"
                      :title="dish.tips"
                    />
                  </div>
                </div>
              </el-col>
            </el-row>
          </div>

          <el-alert
            v-if="dayTips.length"
            class="mt-2"
            type="info"
            :closable="false"
            show-icon
            title="当日饮食建议"
            :description="dayTips.join('；')"
          />
        </el-card>

        <!-- 可选扩展信息 -->
        <el-card>
          <el-tabs v-model="activeTab">
            <el-tab-pane label="健康分析" name="analysis">
              <div class="scroll-area text-sm text-gray-700">
                {{ nutrition.health_analysis || '暂无数据' }}
              </div>
            </el-tab-pane>
            <el-tab-pane label="营养方案" name="plan">
              <div class="scroll-area text-sm text-gray-700">
                {{ nutrition.nutrition_plan || '暂无数据' }}
              </div>
            </el-tab-pane>
            <el-tab-pane label="知识库依据" name="knowledge">
              <div v-if="knowledgeRefs.length" class="space-y-3">
                <div
                  v-for="(k, i) in knowledgeRefs"
                  :key="i"
                  class="p-3 bg-emerald-50 rounded-lg text-sm text-gray-700 leading-6"
                >
                  <div class="flex items-center gap-2 mb-1 flex-wrap">
                    <el-tag size="small" type="success" effect="plain">
                      {{ k.evidence_level ? k.evidence_level + ' 级证据' : '依据' }}
                    </el-tag>
                    <span class="font-medium text-emerald-700">{{ k.source || '营养学依据' }}</span>
                    <span v-if="k.category" class="text-xs text-gray-400">· {{ k.category }}</span>
                  </div>
                  <div class="text-gray-700">{{ k.content }}</div>
                </div>
              </div>
              <el-empty v-else description="暂无引用" :image-size="70" />
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>

      <el-col :span="8">
        <!-- 人工确认闸门 -->
        <el-card class="mb-5" v-if="recipe.status === 'pending_review'">
          <template #header>
            <span class="font-bold">⛨ 人工确认闸门</span>
          </template>
          <el-alert type="warning" :closable="false" show-icon class="mb-3"
            title="待人工确认" description="AI 已生成多日菜单并通过内部审核,请审阅后确认采用;或提出修订意见交回重做。" />
          <div class="flex gap-2">
            <el-button type="success" class="flex-1" :loading="acting === 'approve'" @click="handleApprove">
              ✓ 确认采用
            </el-button>
            <el-button type="warning" class="flex-1" :loading="acting === 'revise'" @click="handleRevise">
              ↺ 请求修订
            </el-button>
          </div>
        </el-card>

        <el-card class="mb-5" v-else-if="recipe.status === 'active' && recipe.review_status === 'approved'">
          <template #header><span class="font-bold">⛨ 确认记录</span></template>
          <div class="text-sm text-gray-600 space-y-1">
            <div>状态:<el-tag type="success" size="small">已确认采用</el-tag></div>
            <div v-if="recipe.reviewed_by">确认人:{{ recipe.reviewed_by }}</div>
            <div v-if="recipe.reviewed_at">确认时间:{{ formatDate(recipe.reviewed_at, true) }}</div>
            <div v-if="recipe.revision_count">修订次数:{{ recipe.revision_count }}</div>
            <div v-if="recipe.review_decision">意见:{{ recipe.review_decision }}</div>
          </div>
        </el-card>

        <!-- 审核结果(代表首日) -->
        <el-card class="mb-5">
          <template #header>
            <span class="font-bold">质量审核结果</span>
          </template>
          <el-alert
            :type="review.passed ? 'success' : 'warning'"
            :closable="false"
            show-icon
            :title="review.passed ? '审核通过' : '存在待优化项'"
            :description="review.rule_summary || ''"
          />
          <div v-if="review.issues?.length" class="mt-3">
            <div class="text-sm font-medium text-gray-700 mb-2">审核意见:</div>
            <ul class="pl-4 m-0 text-sm text-gray-600 space-y-1">
              <li v-for="(issue, i) in review.issues" :key="i" class="list-disc">{{ issue }}</li>
            </ul>
          </div>
          <div v-if="review.llm_verdict" class="mt-3 text-xs text-gray-500 whitespace-pre-wrap">
            {{ review.llm_verdict }}
          </div>
        </el-card>

        <!-- 饮食建议(整体) -->
        <el-card class="mb-5" v-if="overallTips.length">
          <template #header><span class="font-bold">饮食建议</span></template>
          <ul class="pl-4 m-0 text-sm text-gray-600 space-y-2">
            <li v-for="(tip, i) in overallTips" :key="i" class="list-disc leading-6">{{ tip }}</li>
          </ul>
        </el-card>

        <!-- Agent 执行日志 -->
        <el-card>
          <template #header><span class="font-bold">Agent 执行日志</span></template>
          <el-timeline>
            <el-timeline-item
              v-for="(log, i) in agentLog"
              :key="i"
              :timestamp="`步骤 ${i + 1}`"
              :color="logColor(log)"
            >
              <span class="text-sm text-gray-700">{{ log }}</span>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-if="!agentLog.length" description="暂无日志" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Printer } from '@element-plus/icons-vue'
import api from '@/api'
import { formatDate } from '@/utils'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const activeTab = ref('analysis')
const recipe = ref({})
const selectedDay = ref(0)
const acting = ref('')

const nutrition = computed(() => recipe.value.nutrition_info || {})
const menus = computed(() => recipe.value.menus || [])
const currentMenu = computed(() => menus.value[selectedDay.value] || menus.value[0] || null)
const review = computed(() => nutrition.value.review || {})
const agentLog = computed(() => nutrition.value.agent_log || [])
const knowledgeRefs = computed(() => nutrition.value.knowledge_refs || [])

// 跨多日汇总的整体营养(从每日菜单明细累算)
const round1 = (x) => Math.round((Number(x) || 0) * 10) / 10
const overallNutrition = computed(() => {
  let cal = 0, pro = 0, carb = 0, fat = 0, fiber = 0
  for (const m of menus.value) {
    cal += Number(m.total_calories) || 0
    pro += Number(m.total_protein) || 0
    carb += Number(m.total_carbohydrate) || 0
    fat += Number(m.total_fat) || 0
    for (const meal of m.meals || []) {
      for (const d of meal.dishes || []) fiber += Number(d.fiber) || 0
    }
  }
  return {
    calories: cal,
    protein: round1(pro),
    carbs: round1(carb),
    fat: round1(fat),
    fiber: round1(fiber),
  }
})

// 当日备注(JSON: {tips, day_review})
const dayMeta = computed(() => {
  const notes = currentMenu.value?.notes
  if (!notes) return { tips: [], day_review: {} }
  try {
    const obj = typeof notes === 'string' ? JSON.parse(notes) : notes
    return { tips: obj.tips || [], day_review: obj.day_review || {} }
  } catch {
    return { tips: [], day_review: {} }
  }
})
const dayTips = computed(() => dayMeta.value.tips)
const dayReview = computed(() => dayMeta.value.day_review || {})
const overallTips = computed(() => nutrition.value.tips || [])

const statusType = computed(() => {
  if (recipe.value.status === 'pending_review') return 'warning'
  if (recipe.value.status === 'revision_requested') return 'info'
  if (recipe.value.status === 'active') return 'success'
  return 'info'
})
const statusLabel = computed(() => {
  if (recipe.value.status === 'pending_review') return '待人工确认'
  if (recipe.value.status === 'revision_requested') return '重做中'
  if (recipe.value.status === 'active') return '已生效'
  return '已归档'
})

const MEAL_LABEL_MAP = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' }
const mealLabel = (type) => MEAL_LABEL_MAP[type] || type
const mealIcon = (type) =>
  ({ breakfast: '🌅', lunch: '☀️', dinner: '🌙', snack: '🍎' })[type] || '🍽'

const WEEK = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const formatDay = (d) => {
  if (!d) return ''
  const dt = new Date(d)
  return `${d} ${WEEK[dt.getDay()]}`
}

const logColor = (log) => {
  if (log.includes('不通过')) return '#E6A23C'
  if (log.includes('通过')) return '#67C23A'
  return '#409EFF'
}

const handlePrint = () => window.print()

const fetchRecipe = async () => {
  loading.value = true
  try {
    recipe.value = await api.recipes.get(route.params.id)
    selectedDay.value = 0
  } catch {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

const handleApprove = async () => {
  acting.value = 'approve'
  try {
    await api.recipes.approveReview(recipe.value.id, { decision: '人工确认通过' })
    ElMessage.success('已确认采用,食谱生效')
    await fetchRecipe()
  } catch {
    /* 拦截器已提示 */
  } finally {
    acting.value = ''
  }
}

const handleRevise = async () => {
  let notes
  try {
    const { value } = await ElMessageBox.prompt('请填写修订意见(将作为 AI 重做的指令)', '请求修订', {
      confirmButtonText: '提交修订',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputValidator: (v) => (v && v.trim() ? true : '修订意见不能为空')
    })
    notes = value
  } catch {
    return
  }
  acting.value = 'revise'
  try {
    await api.recipes.requestRevision(recipe.value.id, { notes })
    ElMessage.success('已按意见重做,请再次确认')
    await fetchRecipe()
  } catch {
    /* 拦截器已提示 */
  } finally {
    acting.value = ''
  }
}

onMounted(fetchRecipe)
</script>

<style scoped>
@media print {
  .el-button {
    display: none;
  }
}
</style>
