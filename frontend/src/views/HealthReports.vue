<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <div>
        <h2 class="text-2xl font-bold text-gray-800 m-0">健康报告</h2>
        <p class="text-gray-500 text-sm mt-1 mb-0">上传体检报告,系统会自动解析关键健康指标</p>
      </div>
      <el-button type="primary" @click="openDialog">
        <el-icon class="mr-1"><Upload /></el-icon>
        上传报告
      </el-button>
    </div>

    <el-card>
      <el-table :data="reports" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="report_name" label="报告名称" min-width="180" />
        <el-table-column label="血糖 (mmol/L)" width="130" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.blood_glucose" :type="glucoseTagType(row.blood_glucose)">
              {{ row.blood_glucose }}
            </el-tag>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>
        <el-table-column label="血压 (mmHg)" width="140" align="center">
          <template #default="{ row }">
            <el-tag
              v-if="row.blood_pressure_systolic"
              :type="bloodPressureTagType(row.blood_pressure_systolic, row.blood_pressure_diastolic)"
            >
              {{ row.blood_pressure_systolic }}/{{ row.blood_pressure_diastolic }}
            </el-tag>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>
        <el-table-column label="尿酸 (μmol/L)" width="130" align="center">
          <template #default="{ row }">
            {{ row.uric_acid ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="异常项" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.analysis_result?.abnormal_count ? 'danger' : 'success'" size="small">
              {{ row.analysis_result?.abnormal_count ?? 0 }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at, true) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="$router.push(`/health-reports/${row.id}`)">
              查看详情
            </el-button>
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无健康报告" :image-size="90">
            <el-button type="primary" @click="openDialog">上传第一份报告</el-button>
          </el-empty>
        </template>
      </el-table>
    </el-card>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传体检报告" width="640px">
      <el-form :model="uploadForm" label-width="90px">
        <el-form-item label="报告名称" required>
          <el-input v-model="uploadForm.report_name" placeholder="例如:2026 年度体检报告" />
        </el-form-item>
        <el-form-item label="报告内容">
          <el-input
            v-model="uploadForm.report_content"
            type="textarea"
            :rows="10"
            placeholder="可直接粘贴体检报告文本(与下方文件上传二选一)&#10;例如:空腹血糖:7.4 mmol/L&#10;血压:148/95 mmHg&#10;尿酸:486 μmol/L"
          />
          <div class="text-xs text-gray-400 mt-1">
            支持自动识别:血糖、收缩压/舒张压、血压组合值、尿酸、总胆固醇、甘油三酯
          </div>
        </el-form-item>
        <el-form-item label="上传文件">
          <el-upload
            :http-request="handleFileUpload"
            :limit="1"
            :show-file-list="true"
            :before-upload="beforeFileUpload"
            accept=".txt,.md,.pdf"
          >
            <el-button type="primary" plain>
              <el-icon class="mr-1"><Upload /></el-icon>
              选择体检报告(txt/md/pdf)
            </el-button>
          </el-upload>
          <div v-if="uploadForm.file_url" class="text-xs text-green-600 mt-1">
            已上传:{{ uploadForm.file_name }}
            <el-link type="primary" :href="uploadForm.file_url" target="_blank" class="ml-1">
              预览
            </el-link>
          </div>
          <div class="text-xs text-gray-400 mt-1">
            文件经 MinIO 对象存储保存;内容为空时,系统会自动抽取文本并解析
          </div>
        </el-form-item>
        <el-form-item>
          <el-button text type="primary" @click="fillExample">填入示例报告</el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">上传并分析</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import api from '@/api'
import { bloodPressureTagType, formatDate, glucoseTagType } from '@/utils'

const loading = ref(false)
const uploading = ref(false)
const reports = ref([])
const showUploadDialog = ref(false)

const uploadForm = reactive({
  report_name: '',
  report_content: '',
  file_key: '',
  file_url: '',
  file_name: ''
})

const EXAMPLE_REPORT = `常规体检报告
姓名:张三  年龄:45  性别:男
空腹血糖:7.4 mmol/L
血压:148/95 mmHg
尿酸:486 μmol/L
总胆固醇:6.3 mmol/L
甘油三酯:2.6 mmol/L`

const fetchReports = async () => {
  loading.value = true
  try {
    reports.value = await api.healthReports.list()
  } catch {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

const openDialog = () => {
  uploadForm.report_name = ''
  uploadForm.report_content = ''
  uploadForm.file_key = ''
  uploadForm.file_url = ''
  uploadForm.file_name = ''
  showUploadDialog.value = true
}

const fillExample = () => {
  uploadForm.report_name = uploadForm.report_name || '示例体检报告'
  uploadForm.report_content = EXAMPLE_REPORT
}

const beforeFileUpload = (file) => {
  const okTypes = ['txt', 'md', 'pdf']
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!okTypes.includes(ext)) {
    ElMessage.error('仅支持 .txt / .md / .pdf 文件')
    return false
  }
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 20MB')
    return false
  }
  return true
}

const handleFileUpload = async ({ file }) => {
  const fd = new FormData()
  fd.append('file', file)
  try {
    const res = await api.files.upload(fd)
    uploadForm.file_key = res.file_key
    uploadForm.file_url = res.file_url
    uploadForm.file_name = res.file_name
    uploadForm.report_name = uploadForm.report_name || file.name
    ElMessage.success('文件已上传至对象存储,提交后将自动解析')
  } catch {
    /* 拦截器已提示 */
  }
}

const handleUpload = async () => {
  if (!uploadForm.report_name) {
    ElMessage.warning('请填写报告名称')
    return
  }
  if (!uploadForm.report_content && !uploadForm.file_key) {
    ElMessage.warning('请粘贴报告文本,或上传报告文件')
    return
  }
  uploading.value = true
  try {
    const report = await api.healthReports.create({
      report_name: uploadForm.report_name,
      report_content: uploadForm.report_content || undefined,
      file_key: uploadForm.file_key || undefined,
      file_url: uploadForm.file_url || undefined
    })
    const count = report.analysis_result?.abnormal_count ?? 0
    ElMessage.success(count ? `报告解析完成,发现 ${count} 项指标需要关注` : '报告上传成功,各项指标正常')
    showUploadDialog.value = false
    await fetchReports()
  } catch {
    /* 拦截器已提示 */
  } finally {
    uploading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除报告「${row.report_name}」吗?`, '删除确认', {
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    await api.healthReports.remove(row.id)
    ElMessage.success('删除成功')
    await fetchReports()
  } catch {
    /* 拦截器已提示 */
  }
}

onMounted(fetchReports)
</script>
