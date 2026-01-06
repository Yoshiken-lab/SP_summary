<template>
  <div class="page-container monthly-aggregation">
    <div class="page-header">
      <h1>月次集計</h1>
      <p>CSVデータから売上を集計し、Excel報告書を作成します</p>
    </div>

    <el-row :gutter="24" class="main-content-grid">
      <!-- Left Column: File Uploads -->
      <el-col :span="14">
        <el-card class="upload-card" shadow="never">
          <template #header>
            <div class="card-title">
              <span class="step-badge">STEP 1</span>
              <span>ファイル選択</span>
            </div>
          </template>

          <!-- Sales CSV -->
          <div class="upload-section">
            <div class="upload-label">
              <span class="icon">📊</span>
              <span>売上データ (CSV)</span>
              <span v-if="salesFile" class="file-status success">✓</span>
            </div>
            <el-upload
              ref="uploadSalesRef"
              drag
              action="#"
              :limit="1"
              :auto-upload="false"
              :on-change="handleSalesChange"
              :on-remove="handleSalesRemove"
              :on-exceed="handleExceed"
              :show-file-list="false"
              class="drag-upload"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                <span v-if="!salesFile">ファイルをドラッグ&ドロップ</span>
                <span v-else class="file-name">{{ salesFile.name }}</span>
              </div>
            </el-upload>
          </div>

          <!-- Accounts CSV -->
          <div class="upload-section">
            <div class="upload-label">
              <span class="icon">👥</span>
              <span>会員データ (CSV)</span>
              <span v-if="accountsFile" class="file-status success">✓</span>
            </div>
            <el-upload
              ref="uploadAccountsRef"
              drag
              action="#"
              :limit="1"
              :auto-upload="false"
              :on-change="handleAccountsChange"
              :on-remove="handleAccountsRemove"
              :on-exceed="handleExceed"
              :show-file-list="false"
              class="drag-upload"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                <span v-if="!accountsFile">ファイルをドラッグ&ドロップ</span>
                <span v-else class="file-name">{{ accountsFile.name }}</span>
              </div>
            </el-upload>
          </div>

          <!-- Master XLSX -->
          <div class="upload-section">
            <div class="upload-label">
              <span class="icon">📋</span>
              <span>担当者マスタ (XLSX)</span>
              <span v-if="masterFile" class="file-status success">✓</span>
            </div>
            <el-upload
              ref="uploadMasterRef"
              drag
              action="#"
              :limit="1"
              :auto-upload="false"
              :on-change="handleMasterChange"
              :on-remove="handleMasterRemove"
              :on-exceed="handleExceed"
              :show-file-list="false"
              class="drag-upload"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                <span v-if="!masterFile">ファイルをドラッグ&ドロップ</span>
                <span v-else class="file-name">{{ masterFile.name }}</span>
              </div>
            </el-upload>
          </div>
        </el-card>
      </el-col>

      <!-- Right Column: Period Selection & Execution -->
      <el-col :span="10">
        <div class="right-column">
          <!-- Period Selection Card -->
          <el-card class="period-card" shadow="never">
            <template #header>
              <div class="card-title">
                <span class="step-badge">STEP 2</span>
                <span>対象期間</span>
              </div>
            </template>
            <el-form label-position="top">
              <el-form-item label="年度">
                <el-select v-model="options.fiscalYear" placeholder="年度を選択" style="width: 100%">
                  <el-option v-for="year in fiscalYears" :key="year" :label="`${year}年度`" :value="year" />
                </el-select>
              </el-form-item>
              <el-form-item label="月">
                <el-select v-model="options.month" placeholder="月を選択" style="width: 100%">
                  <el-option v-for="month in 12" :key="month" :label="`${month}月`" :value="month" />
                </el-select>
              </el-form-item>
            </el-form>
            <el-button
              type="primary"
              size="large"
              @click="startAggregation"
              :disabled="!canStart"
              :loading="isLoading"
              class="execute-btn"
            >
              <el-icon><Histogram /></el-icon>
              <span>集計を実行</span>
            </el-button>
          </el-card>

          <!-- Log Display -->
          <el-card v-if="logs.length > 0" class="log-card" shadow="never">
            <template #header>
              <div class="card-title">
                <span>ログ</span>
              </div>
            </template>
            <div class="log-area">
              <div v-for="(log, index) in logs" :key="index" class="log-entry" :class="log.type">
                {{ log.message }}
              </div>
            </div>
          </el-card>
        </div>
      </el-col>
    </el-row>

    <!-- 処理中ダイアログ -->
    <el-dialog v-model="monthlyModalVisible" title="月次集計" :close-on-click-modal="false" :show-close="!isLoading">
      <div v-if="isLoading" class="dialog-content">
        <h3 class="dialog-title">月次集計中...</h3>
        <el-progress :percentage="progress" :stroke-width="15" striped />
        <div class="modal-logs">
          <div v-for="(log, index) in logs" :key="index" :class="['modal-log-item', log.status]">
            <el-icon><component :is="getLogIcon(log.status)" /></el-icon>
            <span>{{ log.message }}</span>
          </div>
        </div>
      </div>
       <div v-else>
         <el-result
            icon="success"
            title="月次集計完了！"
            :sub-title="`総売上: ${formatCurrency(result?.total_sales)}`"
          >
            <template #extra>
              <el-button type="primary" @click="closeMonthlyModal">閉じる</el-button>
            </template>
          </el-result>
       </div>
    </el-dialog>

    <!-- マスタ不一致エラーダイアログ -->
     <el-dialog v-model="masterMismatchError" title="担当者マスタ不一致" width="500px">
        <el-alert title="担当者マスタに未登録の学校があります" type="error" :closable="false" show-icon>
            以下の学校が担当者マスタ（XLSX）に登録されていません。<br>
            マスタを更新してから、再度集計を実行してください。
        </el-alert>
        <div class="modal-school-list">
          <div v-for="school in masterMismatchError?.schools" :key="school" class="modal-school-item">
            {{ school }}
          </div>
        </div>
        <template #footer>
          <el-button type="primary" @click="closeMasterMismatchError">
            ファイル選択に戻る
          </el-button>
        </template>
      </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { ElNotification, ElLoading } from 'element-plus';
import { UploadFilled, Histogram, Check, Close, Loading } from '@element-plus/icons-vue';

// --- State ---
const activeStep = ref(0);
const files = ref({ sales: null, accounts: null, master: null });

const uploadSalesRef = ref();
const uploadAccountsRef = ref();
const uploadMasterRef = ref();

const currentDate = new Date();
const currentMonth = currentDate.getMonth() + 1;
const fiscalYear = currentMonth >= 4 ? currentDate.getFullYear() : currentDate.getFullYear() - 1;

const options = ref({
  fiscalYear: fiscalYear,
  month: currentMonth,
});

const isLoading = ref(false);
const progress = ref(0);
const logs = ref([]);
const result = ref(null);
const sessionId = ref(null);

const monthlyModalVisible = ref(false);
const masterMismatchError = ref(null);

// --- Computed ---
const fiscalYears = computed(() => {
  const currentYear = new Date().getFullYear();
  return Array.from({ length: 6 }, (_, i) => currentYear - 4 + i);
});

const salesFile = computed(() => files.value.sales);
const accountsFile = computed(() => files.value.accounts);
const masterFile = computed(() => files.value.master);

const canStart = computed(() => {
  return !!(files.value.sales && files.value.accounts && files.value.master && !isLoading.value);
});

// --- Watcher ---
watch(files, () => {
  if (files.value.sales && files.value.accounts && files.value.master) {
    activeStep.value = 1;
  } else {
    activeStep.value = 0;
  }
}, { deep: true });


// --- Methods ---
const handleExceed = () => {
  ElNotification({
    title: '警告',
    message: 'ファイルは1つしか選択できません。既存のファイルを削除してから再度選択してください。',
    type: 'warning',
  });
};

const handleSalesChange = (file) => { files.value.sales = file.raw; };
const handleSalesRemove = () => { files.value.sales = null; };
const handleAccountsChange = (file) => { files.value.accounts = file.raw; };
const handleAccountsRemove = () => { files.value.accounts = null; };
const handleMasterChange = (file) => { files.value.master = file.raw; };
const handleMasterRemove = () => { files.value.master = null; };


const addLog = (message, status) => {
  logs.value.push({ message, status });
};

const updateLog = (index, message, status) => {
  if (logs.value[index]) {
    logs.value[index].message = message;
    logs.value[index].status = status;
  }
};

const getLogIcon = (status) => {
  switch (status) {
    case 'success': return Check;
    case 'processing': return Loading;
    default: return Close;
  }
};

const formatCurrency = (value) => {
  if (!value && value !== 0) return '-';
  return '¥' + Math.round(value).toLocaleString();
};

const resetForm = () => {
  activeStep.value = 0;
  files.value = { sales: null, accounts: null, master: null };
  progress.value = 0;
  logs.value = [];
  result.value = null;
  sessionId.value = null;
  isLoading.value = false;
  monthlyModalVisible.value = false;
  masterMismatchError.value = null;
  uploadSalesRef.value?.clearFiles();
  uploadAccountsRef.value?.clearFiles();
  uploadMasterRef.value?.clearFiles();
};

const startAggregation = async () => {
  if (!canStart.value) return;

  const loadingInstance = ElLoading.service({
    lock: true,
    text: '集計処理を実行中...',
    background: 'rgba(0, 0, 0, 0.7)',
  });

  isLoading.value = true;
  logs.value = [];
  progress.value = 0;
  monthlyModalVisible.value = true;
  activeStep.value = 2;

  try {
    addLog('ファイルをアップロード中...', 'processing');
    const formData = new FormData();
    formData.append('sales_file', files.value.sales);
    formData.append('accounts_file', files.value.accounts);
    formData.append('master_file', files.value.master);
    const uploadResponse = await fetch('/api/upload', { method: 'POST', body: formData });
    const uploadData = await uploadResponse.json();
    if (uploadData.status !== 'success') throw new Error(uploadData.message);
    sessionId.value = uploadData.session_id;
    updateLog(0, 'ファイルアップロード完了', 'success');
    progress.value = 20;

    addLog('売上データを集計中...', 'processing');
    const aggResponse = await fetch('/api/aggregate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId.value,
        fiscal_year: options.value.fiscalYear,
        month: options.value.month,
      }),
    });
    const aggData = await aggResponse.json();
    if (aggData.status !== 'success') {
      if (aggData.error_type === 'master_mismatch') {
        masterMismatchError.value = { schools: aggData.unmatched_schools };
        throw new Error('MASTER_MISMATCH');
      }
      throw new Error(aggData.message);
    }
    result.value = aggData.summary;
    updateLog(1, '集計完了', 'success');
    progress.value = 100;
    isLoading.value = false;

    ElNotification({
      title: '成功',
      message: '月次集計が完了しました。',
      type: 'success',
    });

  } catch (error) {
    isLoading.value = false;
    activeStep.value = 0;
    if (error.message !== 'MASTER_MISMATCH') {
      monthlyModalVisible.value = false;
      ElNotification({
        title: 'エラー',
        message: error.message || '処理中に予期せぬエラーが発生しました。',
        type: 'error',
      });
    }
  } finally {
    loadingInstance.close();
  }
};

const closeMonthlyModal = () => {
  if (result.value) {
    resetForm();
  }
  monthlyModalVisible.value = false;
};

const closeMasterMismatchError = () => {
  masterMismatchError.value = null;
  resetForm();
};

</script>


<style scoped>
/* Page Layout */
.monthly-aggregation {
  padding: 0;
}

.page-header {
  padding: var(--space-xl);
  padding-bottom: var(--space-lg);
  border-bottom: 1px solid var(--border-color);
}

.page-header h1 {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-sm) 0;
}

.page-header p {
  color: var(--text-secondary);
  margin: 0;
  font-size: 0.9rem;
}

/* Main Content Grid */
.main-content-grid {
  padding: var(--space-xl);
}

/* Card Styles */
.upload-card,
.period-card,
.log-card {
  height: auto;
}

.card-title {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.step-badge {
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  padding: 2px 10px;
  border-radius: var(--radius-sm);
  font-size: 0.7rem;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-weight: 500;
  letter-spacing: 0.5px;
}

/* Upload Sections */
.upload-section {
  margin-bottom: var(--space-lg);
}

.upload-section:last-child {
  margin-bottom: 0;
}

.upload-label {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-primary);
}

.upload-label .icon {
  font-size: 1.2rem;
}

.file-status {
  margin-left: auto;
  font-size: 1.2rem;
  font-weight: bold;
}

.file-status.success {
  color: var(--accent-green);
}

/* Drag & Drop Upload */
.drag-upload {
  width: 100%;
}

.drag-upload :deep(.el-upload-dragger) {
  width: 100%;
  height: 100px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-input);
  transition: all var(--transition-fast);
}

.drag-upload :deep(.el-upload-dragger:hover) {
  border-color: var(--accent-blue);
  background: rgba(88, 166, 255, 0.05);
}

.drag-upload :deep(.el-icon--upload) {
  font-size: 2rem;
  color: var(--text-secondary);
  margin-bottom: var(--space-sm);
}

.drag-upload :deep(.el-upload__text) {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.file-name {
  color: var(--accent-blue) !important;
  font-weight: 500;
}

/* Right Column */
.right-column {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  height: 100%;
}

/* Period Card */
.period-card {
  flex-shrink: 0;
}

.period-card :deep(.el-form-item) {
  margin-bottom: var(--space-md);
}

.period-card :deep(.el-form-item:last-child) {
  margin-bottom: 0;
}

.period-card :deep(.el-form-item__label) {
  color: var(--text-secondary);
  font-size: 0.85rem;
  margin-bottom: var(--space-sm);
}

/* Execute Button */
.execute-btn {
  width: 100%;
  margin-top: var(--space-md);
  background: var(--gradient-purple) !important;
  border: none !important;
  font-weight: 600;
  padding: var(--space-md) var(--space-lg);
}

.execute-btn:hover {
  filter: brightness(1.1);
}

.execute-btn:disabled {
  background: var(--bg-input) !important;
  color: var(--text-tertiary) !important;
  filter: none;
}

/* Log Card */
.log-card {
  flex: 1;
  min-height: 200px;
}

.log-area {
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-md);
  max-height: 300px;
  overflow-y: auto;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.log-entry {
  margin-bottom: var(--space-xs);
  color: var(--text-secondary);
  line-height: 1.6;
}

.log-entry:last-child {
  margin-bottom: 0;
}

.log-entry.info {
  color: var(--text-primary);
}

.log-entry.success {
  color: var(--accent-green);
}

.log-entry.error {
  color: var(--accent-red);
}

.log-entry.warning {
  color: var(--accent-orange);
}

/* Dialog Styles */
.dialog-title {
  text-align: center;
  font-size: 1.2rem;
  margin-bottom: var(--space-lg);
  color: var(--text-primary);
}

.modal-logs {
  margin-top: var(--space-lg);
  padding: var(--space-md);
  background-color: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  max-height: 150px;
  overflow-y: auto;
  font-size: 0.9rem;
}

.modal-log-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-xs);
  color: var(--text-secondary);
}

.modal-school-list {
  margin-top: var(--space-md);
  max-height: 200px;
  overflow-y: auto;
  background-color: rgba(218, 54, 51, 0.1);
  border: 1px solid var(--accent-red);
  padding: var(--space-sm);
  border-radius: var(--radius-sm);
}

.modal-school-item {
  color: var(--text-primary);
  padding: var(--space-xs) 0;
}

:deep(.el-result__subtitle) {
  color: var(--text-secondary);
}
</style>