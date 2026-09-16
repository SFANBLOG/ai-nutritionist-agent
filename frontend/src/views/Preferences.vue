<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <div>
        <h2 class="text-2xl font-bold text-gray-800 m-0">口味偏好</h2>
        <p class="text-gray-500 text-sm mt-1 mb-0">
          记录您的饮食偏好与禁忌,AI 生成食谱时会自动规避并优先满足
        </p>
      </div>
      <el-button type="primary" :icon="Plus" @click="showDialog = true">新增偏好</el-button>
    </div>

    <el-card>
      <el-row :gutter="20">
        <el-col v-for="group in groupedPreferences" :key="group.type" :span="12" class="mb-5">
          <div class="border border-gray-200 rounded-lg p-4 h-full">
            <div class="flex items-center gap-2 mb-3">
              <el-tag :type="group.color" effect="dark" size="small">{{ group.label }}</el-tag>
              <span class="text-gray-400 text-xs">{{ group.items.length }} 项</span>
            </div>
            <div v-if="group.items.length" class="flex flex-wrap gap-2">
              <el-tag
                v-for="item in group.items"
                :key="item.id"
                :type="group.color"
                effect="light"
                closable
                @close="handleDelete(item)"
              >
                {{ item.preference_value }}
              </el-tag>
            </div>
            <div v-else class="text-gray-400 text-sm">暂无记录</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-dialog v-model="showDialog" title="新增口味偏好" width="480px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="偏好类型" required>
          <el-select v-model="form.preference_type" placeholder="请选择类型" class="w-full">
            <el-option
              v-for="t in PREFERENCE_TYPES"
              :key="t.value"
              :label="t.label"
              :value="t.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input
            v-model="form.preference_value"
            :placeholder="placeholderText"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import api from '@/api'
import { PREFERENCE_TYPES } from '@/utils'

const loading = ref(false)
const saving = ref(false)
const showDialog = ref(false)
const preferences = ref([])

const form = reactive({
  preference_type: 'favorite_food',
  preference_value: ''
})

const placeholderText = computed(
  () => PREFERENCE_TYPES.find((t) => t.value === form.preference_type)?.label + ',例如:西兰花'
)

const groupedPreferences = computed(() =>
  PREFERENCE_TYPES.map((t) => ({
    ...t,
    items: preferences.value.filter((p) => p.preference_type === t.value)
  }))
)

const fetchPreferences = async () => {
  loading.value = true
  try {
    preferences.value = await api.preferences.list()
  } catch {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  if (!form.preference_value.trim()) {
    ElMessage.warning('请填写偏好内容')
    return
  }
  saving.value = true
  try {
    await api.preferences.create({
      preference_type: form.preference_type,
      preference_value: form.preference_value.trim()
    })
    ElMessage.success('保存成功')
    showDialog.value = false
    form.preference_value = ''
    await fetchPreferences()
  } catch {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

const handleDelete = async (item) => {
  try {
    await ElMessageBox.confirm(`确认删除偏好「${item.preference_value}」吗?`, '删除确认', {
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    await api.preferences.remove(item.id)
    ElMessage.success('删除成功')
    await fetchPreferences()
  } catch {
    /* 拦截器已提示 */
  }
}

onMounted(fetchPreferences)
</script>
