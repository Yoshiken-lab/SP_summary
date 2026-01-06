<template>
  <div class="page-container cumulative-aggregation">
    <div class="page-header">
      <h1>累積集計</h1>
      <p>複数の月次集計ファイルを元に、年度の累積報告書を作成します</p>
    </div>

    <el-row :gutter="24" class="main-content-grid">
      <el-col :span="14">
        <el-card class="upload-card" shadow="never">
          <template #header>
            <div class="card-title">
              <span class="step-badge">STEP 1</span>
              <span>月次集計ファイルの追加</span>
            </div>
          </template>

          <el-upload
            drag
            multiple
            action="#"
            :auto-upload="false"
            :on-change="handleFilesChange"
            :show-file-list="false"
            class="drag-upload"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              <span>ファイルをドラッグ&ドロップ（複数可）</span>
            </div>
          </el-upload>

          <div v-if="cumulativeInputFiles.length > 0" class="file-list-section">
            <div class="section-header">
              <span class="step-badge">STEP 2</span>
              <span>追加されたファイル ({{ cumulativeInputFiles.length }}件)</span>
            </div>
            <el-table :data="cumulativeInputFiles" style="width: 100%">
              <el-table-column prop="file.name" label="ファイル名" />
              <el-table-column label="対象年月" width="220">
                <template #default="scope">
                  <el-date-picker
                    v-model="scope.row.period"
                    type="month"
                    placeholder="年月を選択"
                    format="YYYY年M月"
                    value-format="YYYY-M"
                  />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80" align="center">
                <template #default="scope">
                  <el-button type="danger" :icon="Delete" circle @click="removeInputFile(scope.$index)" />
                </template>
              </el-table-column>
            </el-table>
            <div v-if="calculatedFiscalYear" class="fiscal-year-info">
              対象年度: <strong>{{ calculatedFiscalYear }}年度</strong>
              （出力ファイル: SP_年度累計_{{ calculatedFiscalYear }}.xlsx）
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="10">
        <div class="right-column">
          <el-card class="option-card" shadow="never">
            <template #header>
              <div class="card-title">
                <span class="step-badge">STEP 3</span>
                <span>既存ファイル（オプション）</span>
              </div>
            </template>
            <el-upload
              ref="uploadExistingRef"
              action="#"
              :limit="1"
              :auto-upload="false"
              :on-change="handleExistingFileChange"
              :on-remove="handleExistingFileRemove"
            >
              <el-button><el-icon><FolderOpened /></el-icon> ファイルを選択</el-button>
              <template #tip>
                <div class="el-upload__tip">
                  既存のファイルに追記・上書きする場合に選択
                </div>
              </template>
            </el-upload>
            <el-button
              type="primary"
              size="large"
              @click="startCumulativeAggregation"
              :disabled="!canStartCumulative"
              :loading="isLoading"
              class="execute-btn"
            >
              <el-icon><Histogram /></el-icon>
              <span>累積集計を実行 ({{ cumulativeInputFiles.length }}件)</span>
            </el-button>
          </el-card>
        </div>
      </el-col>
    </el-row>

     <!-- 処理中ダイアログ -->
    <el-dialog v-model="cumulativeModalVisible" title="累積集計" :close-on-click-modal="false" :show-close="!isLoading">
       <div v-if="isLoading">
          <h3 class="dialog-title">累積集計中...</h3>
          <el-progress :percentage="cumulativeProgress" :stroke-width="15" striped />
          <div class="modal-logs">
            <div v-for="(log, index) in cumulativeLogs" :key="index" :class="['modal-log-item', log.status]">
               <el-icon><component :is="getLogIcon(log.status)" /></el-icon>
              <span>{{ log.message }}</span>
            </div>
          </div>
       </div>
        <div v-else>
         <el-result
            icon="success"
            title="累積集計完了！"
            :sub-title="`対象年度: ${cumulativeResult?.fiscalYear}年度`"
          >
            <template #info>
                <div class="result-info">
                    <p>処理ファイル数: {{ cumulativeResult?.processedCount }}件</p>
                    <p>追記月: {{ cumulativeResult?.processedMonths }}</p>
                    <p>保存先: <el-tag type="info">{{ cumulativeResult?.outputPath }}</el-tag></p>
                </div>
            </template>
            <template #extra>
              <el-button type="primary" @click="closeCumulativeModal">閉じる</el-button>
            </template>
          </el-result>
       </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { ElNotification, ElLoading } from 'element-plus';
import { UploadFilled, Delete, FolderOpened, Histogram, Check, Close, Loading } from '@element-plus/icons-vue';

// --- State ---
const isLoading = ref(false);
const cumulativeInputFiles = ref([]);
const existingFile = ref(null);
const uploadExistingRef = ref();

const cumulativeProgress = ref(0);
const cumulativeLogs = ref([]);
const cumulativeResult = ref(null);
const cumulativeSessionId = ref(null);
const cumulativeModalVisible = ref(false);


// --- Computed ---
const calculatedFiscalYear = computed(() => {
  if (cumulativeInputFiles.value.length === 0) return null;
  const firstFileWithPeriod = cumulativeInputFiles.value.find(f => f.period);
  if (!firstFileWithPeriod) return null;

  const [year, month] = firstFileWithPeriod.period.split('-').map(Number);
  return month >= 4 ? year : year - 1;
});

const canStartCumulative = computed(() => {
  return cumulativeInputFiles.value.length > 0 && cumulativeInputFiles.value.every(f => f.period) && !isLoading.value;
});

// --- Methods ---
const handleFilesChange = (file, fileList) => {
    // 既存のファイルリストにない新しいファイルのみを追加
    const newFiles = fileList.filter(f => !cumulativeInputFiles.value.some(existing => existing.uid === f.uid));
    newFiles.forEach(f => {
        cumulativeInputFiles.value.push({
            uid: f.uid,
            file: f.raw,
            period: ''
        });
    });
};

const removeInputFile = (index) => {
  cumulativeInputFiles.value.splice(index, 1);
};

const handleExistingFileChange = (file) => {
  existingFile.value = file.raw;
};

const handleExistingFileRemove = () => {
  existingFile.value = null;
};

const getLogIcon = (status) => {
  switch (status) {
    case 'success': return Check;
    case 'processing': return Loading;
    default: return Close;
  }
};

const addCumulativeLog = (message, status) => {
  cumulativeLogs.value.push({ message, status });
};

const updateCumulativeLog = (index, message, status) => {
  if (cumulativeLogs.value[index]) {
    cumulativeLogs.value[index].message = message;
    cumulativeLogs.value[index].status = status;
  }
};

const resetForm = () => {
  isLoading.value = false;
  cumulativeInputFiles.value = [];
  existingFile.value = null;
  uploadExistingRef.value?.clearFiles();
  cumulativeProgress.value = 0;
  cumulativeLogs.value = [];
  cumulativeResult.value = null;
  cumulativeSessionId.value = null;
  cumulativeModalVisible.value = false;
};

const startCumulativeAggregation = async () => {
  if (!canStartCumulative.value) return;

  const loadingInstance = ElLoading.service({
    lock: true,
    text: '累積集計処理を実行中...',
    background: 'rgba(0, 0, 0, 0.7)',
  });

  isLoading.value = true;
  cumulativeLogs.value = [];
  cumulativeProgress.value = 0;
  cumulativeModalVisible.value = true;

  try {
    addCumulativeLog('ファイルをアップロード中...', 'processing');
    const formData = new FormData();
    const filesInfo = cumulativeInputFiles.value.map((item, index) => {
      formData.append(`input_file_${index}`, item.file);
      const [year, month] = item.period.split('-').map(Number);
      return { index, year, month };
    });

    formData.append('files_info', JSON.stringify(filesInfo));
    formData.append('fiscal_year', calculatedFiscalYear.value);

    if (existingFile.value) {
      formData.append('existing_file', existingFile.value);
    }
    
    const uploadResponse = await fetch('/api/cumulative/upload-multiple', {
      method: 'POST',
      body: formData,
    });
    const uploadData = await uploadResponse.json();
    if (uploadData.status !== 'success') throw new Error(uploadData.message);
    cumulativeSessionId.value = uploadData.session_id;
    updateCumulativeLog(0, 'ファイルアップロード完了', 'success');
    cumulativeProgress.value = 30;

    addCumulativeLog('累積集計を実行中...', 'processing');
    const aggResponse = await fetch('/api/cumulative/aggregate-multiple', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: cumulativeSessionId.value }),
    });
    const aggData = await aggResponse.json();
    if (aggData.status !== 'success') throw new Error(aggData.message);
    
    cumulativeResult.value = aggData;
    updateCumulativeLog(1, '累積集計完了', 'success');
    cumulativeProgress.value = 100;
    isLoading.value = false;

     ElNotification({
      title: '成功',
      message: '累積集計が完了しました。',
      type: 'success',
    });

  } catch (error) {
    isLoading.value = false;
    cumulativeModalVisible.value = false;
    ElNotification({
        title: 'エラー',
        message: error.message || '処理中に予期せぬエラーが発生しました。',
        type: 'error',
    });
  } finally {
    loadingInstance.close();
  }
};

const closeCumulativeModal = () => {
    if(!isLoading.value) {
        resetForm();
        cumulativeModalVisible.value = false;
    }
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
.step-label {
    font-size: 1.1rem;
    font-weight: bold;
    display: flex;
    align-items: center;
}
.step-label::before {
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
  padding: var(--space-lg) var(--space-md);
}

/* Card Styles */
.upload-card,
.option-card {
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
  background: rgba(88, 166, 255, 0.1);
  border: 1px solid rgba(88, 166, 255, 0.3);
  padding: 2px 10px;
  border-radius: var(--radius-sm);
  font-size: 0.7rem;
  color: var(--accent-blue);
  font-family: var(--font-mono);
  font-weight: 600;
  letter-spacing: 0.5px;
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
  border: 2px dashed rgba(75, 85, 99, 0.5) !important;
  border-radius: var(--radius-md);
  background: var(--bg-input) !important;
  transition: all var(--transition-fast);
}

.drag-upload :deep(.el-upload-dragger:hover) {
  border-color: var(--accent-blue) !important;
  background: rgba(88, 166, 255, 0.05) !important;
}

.drag-upload :deep(.el-icon--upload) {
  font-size: 2rem;
  color: var(--text-primary) !important;
  margin-bottom: var(--space-sm);
}

.drag-upload :deep(.el-upload__text) {
  color: var(--text-primary) !important;
  font-size: 0.85rem;
}

/* File List Section */
.file-list-section {
  margin-top: var(--space-xl);
}

.section-header {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-bottom: var(--space-md);
  font-weight: 600;
  color: var(--text-primary);
}

/* Fiscal Year Info */
.fiscal-year-info {
  margin-top: var(--space-md);
  background-color: rgba(88, 166, 255, 0.1);
  border: 1px solid rgba(88, 166, 255, 0.3);
  color: var(--accent-blue);
  padding: var(--space-md);
  border-radius: var(--radius-md);
  font-size: 0.9rem;
}

.fiscal-year-info strong {
  color: var(--text-primary);
  font-weight: 700;
}

/* Right Column */
.right-column {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

/* Option Card */
.option-card {
  flex-shrink: 0;
}

.option-card :deep(.el-upload__tip) {
  color: var(--text-secondary);
  font-size: 0.8rem;
  margin-top: var(--space-sm);
}

/* Execute Button */
.execute-btn {
  width: 100%;
  margin-top: var(--space-lg);
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

/* Dialog Styles */
.dialog-title {
  text-align: center;
  font-size: 1.2rem;
  margin-bottom: var(--space-lg);
  color: var(--text-primary);
}

.page-header {
  padding: var(--space-lg) var(--space-md);
  padding-bottom: var(--space-md);
  border-bottom: 1px solid var(--border-color);
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

.result-info p {
  margin: var(--space-xs) 0;
  color: var(--text-secondary);
}

:deep(.el-result__subtitle) {
  color: var(--text-secondary);
}
</style>
```
