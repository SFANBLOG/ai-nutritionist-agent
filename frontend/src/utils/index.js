/** 通用工具函数 */

export const formatDate = (dateStr, withTime = false) => {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  if (Number.isNaN(d.getTime())) return dateStr
  return withTime ? d.toLocaleString('zh-CN') : d.toLocaleDateString('zh-CN')
}

/** 指标等级 -> Element Plus tag 类型 */
export const levelToTagType = (level) => {
  if (!level) return 'info'
  if (level === '正常') return 'success'
  if (level.includes('偏低')) return 'info'
  if (level.includes('边缘') || level.includes('正常高值')) return 'warning'
  return 'danger'
}

/** 血糖水平 -> tag 类型 */
export const glucoseTagType = (value) => {
  if (value === null || value === undefined || value === '') return 'info'
  const v = Number(value)
  if (Number.isNaN(v)) return 'info'
  if (v < 3.9) return 'warning'
  if (v <= 6.1) return 'success'
  if (v < 7.0) return 'warning'
  return 'danger'
}

/** 血压水平 -> tag 类型 */
export const bloodPressureTagType = (systolic, diastolic) => {
  if (!systolic || !diastolic) return 'info'
  if (systolic >= 140 || diastolic >= 90) return 'danger'
  if (systolic >= 120 || diastolic >= 80) return 'warning'
  return 'success'
}

/** 餐次标签 */
export const MEAL_LABELS = {
  breakfast: '早餐',
  lunch: '午餐',
  dinner: '晚餐',
  snack: '加餐'
}

export const mealLabel = (type) => MEAL_LABELS[type] || type || '餐次'

/** 偏好类型中文名 */
export const PREFERENCE_TYPES = [
  { value: 'favorite_food', label: '喜爱食材', color: 'success' },
  { value: 'disliked_food', label: '忌口食材', color: 'warning' },
  { value: 'cuisine', label: '偏好菜系', color: 'primary' },
  { value: 'allergy', label: '过敏食材', color: 'danger' },
  { value: 'goal', label: '健康目标', color: 'info' }
]

export const preferenceLabel = (type) =>
  PREFERENCE_TYPES.find((t) => t.value === type)?.label || type

export const preferenceColor = (type) =>
  PREFERENCE_TYPES.find((t) => t.value === type)?.color || 'info'

/** 复制文本到剪贴板 */
export const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}
