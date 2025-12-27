<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <h1>月次集計</h1>
          <p>CSVデータから売上を集計し、Excel報告書を作成します</p>
        </div>
      </template>

      <el-steps :active="activeStep" finish-status="success" align-center style="margin-bottom: 30px">
        <el-step title="ファイル選択" />
        <el-step title="期間選択" />
        <el-step title="集計実行" />
      </el-steps>

      <el-row :gutter="20">
        <!-- Left Column: File Uploads -->
        <el-col :span="12">
          <el-form label-position="top" class="form-container">
            <el-form-item label="1. 売上データ (CSV)">
               <el-upload
                ref="uploadSalesRef"
                action="#"
                :limit="1"
                :auto-upload="false"
                :on-change="handleSalesChange"
                :on-remove="handleSalesRemove"
                :on-exceed="handleExceed"
              >
                <el-button type="primary"><el-icon><Upload /></el-icon> ファイルを選択</el-button>
              </el-upload>
            </el-form-item>
            <el-form-item label="2. 会員データ (CSV)">
              <el-upload
                ref="uploadAccountsRef"
                action="#"
                :limit="1"
                :auto-upload="false"
                :on-change="handleAccountsChange"
                :on-remove="handleAccountsRemove"
                :on-exceed="handleExceed"
              >
                <el-button type="primary"><el-icon><Upload /></el-icon> ファイルを選択</el-button>
              </el-upload>
            </el-form-item>
            <el-form-item label="3. 担当者マスタ (XLSX)">
              <el-upload
                ref="uploadMasterRef"
                action="#"
                :limit="1"
                :auto-upload="false"
                :on-change="handleMasterChange"
                :on-remove="handleMasterRemove"
                :on-exceed="handleExceed"
              >
                <el-button type="primary"><el-icon><Upload /></el-icon> ファイルを選択</el-button>
              </el-upload>
            </el-form-item>
          </el-form>
        </el-col>

        <!-- Right Column: Options & Action -->
        <el-col :span="12">
          <div class="options-action-panel">
            <el-form label-position="top">
              <el-form-item label="4. 対象期間の選択">
                <el-col :span="11">
                  <el-select v-model="options.fiscalYear" placeholder="年度">
                    <el-option v-for="year in fiscalYears" :key="year" :label="`${year}年度`" :value="year" />
                  </el-select>
                </el-col>
                <el-col class="text-center" :span="2">-</el-col>
                <el-col :span="11">
                  <el-select v-model="options.month" placeholder="月">
                    <el-option v-for="month in 12" :key="month" :label="`${month}月`" :value="month" />
                  </el-select>
                </el-col>
              </el-form-item>
              <el-form-item>
                 <div class="action-box">
                    <el-button
                      type="primary"
                      size="large"
                      @click="startAggregation"
                      :disabled="!canStart"
                      :loading="isLoading"
                    >
                      <el-icon><Promotion /></el-icon>
                      <span>集計を実行</span>
                    </el-button>
                 </div>
              </el-form-item>
            </el-form>
          </div>
        </el-col>
      </el-row>
    </el-card>

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
import { Upload, Promotion, Check, Close, Loading } from '@element-plus/icons-vue';

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
.page-container {
  padding: 20px;
}
.card-header h1 {
  margin: 0;
  font-size: 1.5rem;
}
.card-header p {
  margin: 5px 0 0 0;
  color: var(--el-text-color-secondary);
  font-size: 0.9rem;
}
.el-form-item {
    margin-bottom: 25px;
}
.options-action-panel {
  padding: 20px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  height: 100%;
}
.action-box {
    text-align: center;
    margin-top: 2rem;
}
.el-select {
  width: 100%;
}
.text-center {
  text-align: center;
  line-height: 32px;
}
.dialog-content {
  padding: 10px;
}
.dialog-title {
  text-align: center;
  font-size: 1.2rem;
  margin-bottom: 1.5rem;
  color: var(--el-text-color-primary);
}
.modal-logs {
  margin-top: 1.5rem;
  padding: 10px;
  background-color: #f9fafb;
  border-radius: 4px;
  max-height: 150px;
  overflow-y: auto;
  font-size: 0.9rem;
}
.modal-log-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
  color: var(--el-text-color-regular);
}
.modal-school-list {
  margin-top: 1rem;
  max-height: 200px;
  overflow-y: auto;
  background-color: #fef0f0;
  padding: 8px;
  border-radius: 4px;
}
.modal-school-item {
  color: var(--el-text-color-primary);
}
:deep(.el-result__subtitle) {
  color: var(--el-text-color-regular);
}
</style>