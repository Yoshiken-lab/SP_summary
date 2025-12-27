<template>
  <div class="page-container">
    <el-row :gutter="20">
      <!-- Left Column: Main Actions -->
      <el-col :span="16">
        <!-- Step 1: Data Upload -->
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span class="step-label">1</span>
              <span>データ反映</span>
            </div>
          </template>
          <el-upload
            drag
            multiple
            action="#"
            :auto-upload="false"
            :on-change="handleFileChange"
            :show-file-list="false"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">ここに作成した報告書ファイル(.xlsx)をドラッグ＆ドロップまたは<em>クリック</em></div>
          </el-upload>
          <el-table :data="publishFiles" style="width: 100%; margin-top: 20px" v-if="publishFiles.length > 0">
            <el-table-column prop="name" label="ファイル名" />
            <el-table-column label="操作" width="80" align="center">
              <template #default="scope">
                <el-button type="danger" :icon="Delete" circle @click="removePublishFile(scope.$index)" />
              </template>
            </el-table-column>
          </el-table>
          <div style="text-align: center; margin-top: 20px;">
            <el-button type="primary" size="large" @click="startPublish" :disabled="publishFiles.length === 0" :loading="isPublishing">
              <el-icon><DataAnalysis /></el-icon> 実績を反映 ({{ publishFiles.length }}件)
            </el-button>
          </div>
        </el-card>

        <!-- Step 2: Manager Settings -->
        <el-card class="box-card">
           <template #header>
            <div class="card-header">
              <span class="step-label">2</span>
              <span>担当者設定 (オプション)</span>
            </div>
          </template>
          <el-tabs v-model="settingsTab">
            <el-tab-pane name="alias">
              <template #label>
                <el-icon><User /></el-icon> 担当者名の変換
              </template>
              <p class="tab-description">同一人物で担当者名が異なる場合（例: 「佐藤」→「佐藤（邦）」）の変換ルールを設定します。</p>
              <el-form :inline="true" :model="newAlias">
                <el-form-item label="変換元">
                  <el-input v-model="newAlias.from" placeholder="例: 佐藤" />
                </el-form-item>
                <el-form-item label="変換先">
                  <el-input v-model="newAlias.to" placeholder="例: 佐藤（邦）" />
                </el-form-item>
                <el-form-item>
                  <el-button type="success" @click="addSalesmanAlias" :loading="addingAlias">追加</el-button>
                </el-form-item>
              </el-form>
              <el-collapse v-if="salesmanAliases.length > 0" style="margin-top: 20px;">
                <el-collapse-item :title="`登録済みルール (${salesmanAliases.length}件)`">
                  <el-table :data="salesmanAliases" size="small">
                    <el-table-column prop="from_name" label="変換元" />
                    <el-table-column prop="to_name" label="変換先" />
                    <el-table-column label="登録日" width="120">
                      <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
                    </el-table-column>
                    <el-table-column label="操作" width="80" align="center">
                       <template #default="scope">
                         <el-popconfirm title="このルールを削除しますか？" @confirm="deleteSalesmanAlias(scope.row.id)">
                          <template #reference>
                            <el-button type="danger" :icon="Delete" circle size="small" />
                          </template>
                        </el-popconfirm>
                       </template>
                    </el-table-column>
                  </el-table>
                </el-collapse-item>
              </el-collapse>
            </el-tab-pane>

            <el-tab-pane name="override">
              <template #label>
                <el-icon><OfficeBuilding /></el-icon> 学校担当者の変更
              </template>
              <p class="tab-description">特定の学校・期間の担当者を変更します。既存の売上データも自動更新されます。</p>
              <el-form :model="newOverride" label-position="top">
                <el-row :gutter="20">
                  <el-col :span="12">
                     <el-form-item label="学校名">
                        <el-select
                          v-model="newOverride.school"
                          filterable
                          remote
                          reserve-keyword
                          placeholder="学校名で検索"
                          :remote-method="searchSchools"
                          :loading="schoolSearchLoading"
                          value-key="id"
                          style="width: 100%;"
                        >
                          <el-option v-for="item in schoolOptions" :key="item.id" :label="item.school_name" :value="item" />
                        </el-select>
                      </el-form-item>
                  </el-col>
                  <el-col :span="12">
                    <el-form-item label="担当者">
                      <el-select v-model="newOverride.manager" placeholder="担当者を選択" style="width: 100%;">
                         <el-option v-for="manager in availableManagers" :key="manager" :label="manager" :value="manager" />
                      </el-select>
                    </el-form-item>
                  </el-col>
                  <el-col :span="12">
                     <el-form-item label="対象年度">
                        <el-select v-model="newOverride.fiscalYear" placeholder="年度を選択" style="width: 100%;">
                          <el-option v-for="year in availableFiscalYears" :key="year" :label="`${year}年度`" :value="year" />
                        </el-select>
                      </el-form-item>
                  </el-col>
                   <el-col :span="12">
                      <el-form-item label="対象期間">
                        <el-date-picker
                          v-model="newOverride.period"
                          type="monthrange"
                          range-separator="～"
                          start-placeholder="開始月"
                          end-placeholder="終了月"
                           format="YYYY/MM"
                          value-format="YYYY-M"
                        />
                      </el-form-item>
                  </el-col>
                </el-row>
                <el-form-item>
                  <el-button type="success" @click="addSchoolManagerOverride" :loading="addingOverride">設定を追加</el-button>
                </el-form-item>
              </el-form>
               <el-collapse v-if="schoolManagerOverrides.length > 0" style="margin-top: 20px;">
                <el-collapse-item :title="`登録済み設定 (${schoolManagerOverrides.length}件)`">
                   <el-table :data="schoolManagerOverrides" size="small">
                    <el-table-column prop="school_name" label="学校名" />
                    <el-table-column prop="fiscal_year" label="年度" width="80"/>
                    <el-table-column label="期間" width="180">
                      <template #default="scope">
                        {{ scope.row.start_month }}月 〜 {{ scope.row.end_month ? `${scope.row.end_month}月` : '継続中' }}
                      </template>
                    </el-table-column>
                    <el-table-column prop="manager" label="設定担当者" />
                     <el-table-column prop="original_manager" label="元担当者" />
                    <el-table-column label="登録日" width="120">
                       <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
                    </el-table-column>
                    <el-table-column label="操作" width="80" align="center">
                      <template #default="scope">
                         <el-popconfirm title="この設定を削除しますか？" @confirm="deleteSchoolManagerOverride(scope.row.id)">
                          <template #reference>
                            <el-button type="danger" :icon="Delete" circle size="small" />
                          </template>
                        </el-popconfirm>
                       </template>
                    </el-table-column>
                  </el-table>
                </el-collapse-item>
              </el-collapse>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>

      <!-- Right Column: Status & Publish -->
      <el-col :span="8">
        <el-card class="box-card">
           <template #header>
            <div class="card-header">
               <span class="step-label">3</span>
              <span>ダッシュボード公開</span>
            </div>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="最終生成日時">
                <el-tag size="small">{{ formatDateTime(dashboardStatus.lastGenerated) || '未生成' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="最終公開日時">
                <el-tag size="small">{{ formatDateTime(dashboardStatus.lastPublished) || '未公開' }}</el-tag>
            </el-descriptions-item>
             <el-descriptions-item label="状態">
                <el-tag v-if="dashboardStatus.hasUnpublishedChanges" type="warning" size="small">未公開の変更あり</el-tag>
                <el-tag v-else type="success" size="small">公開済み</el-tag>
            </el-descriptions-item>
          </el-descriptions>
          <div class="action-buttons">
             <el-button @click="previewDashboard" :disabled="!dashboardStatus.lastGenerated">
                <el-icon><View /></el-icon> プレビュー
            </el-button>
             <el-button type="primary" @click="publishToInternalServer" :disabled="!dashboardStatus.lastGenerated" :loading="isPublishingToServer">
                <el-icon><Promotion /></el-icon> 社内サーバーに公開
            </el-button>
          </div>
           <div v-if="dashboardStatus.publishUrl" class="publish-url-box">
             <el-input :value="dashboardStatus.publishUrl" readonly>
                <template #prepend>公開URL</template>
                <template #append><el-button @click="copyPublishUrl">コピー</el-button></template>
            </el-input>
           </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { ElNotification, ElMessageBox, ElLoading } from 'element-plus';
import { UploadFilled, Delete, User, OfficeBuilding, View, Promotion, DataAnalysis } from '@element-plus/icons-vue';

// --- Reactive State ---
const publishFiles = ref([]);
const isPublishing = ref(false);
const settingsTab = ref('alias');

const newAlias = reactive({ from: '', to: '' });
const salesmanAliases = ref([]);
const addingAlias = ref(false);

const newOverride = reactive({ school: null, manager: '', fiscalYear: new Date().getFullYear(), period: '' });
const schoolManagerOverrides = ref([]);
const addingOverride = ref(false);
const schoolOptions = ref([]);
const schoolSearchLoading = ref(false);
const availableManagers = ref([]);

const dashboardStatus = ref({});
const isPublishingToServer = ref(false);


// --- Computed ---
const availableFiscalYears = computed(() => {
  const currentYear = new Date().getFullYear();
  return Array.from({ length: 6 }, (_, i) => currentYear - 4 + i);
});

// --- Methods ---
const formatDate = (dateStr) => dateStr ? new Date(dateStr).toLocaleDateString('ja-JP') : '';
const formatDateTime = (dateStr) => dateStr ? new Date(dateStr).toLocaleString('ja-JP') : '';

// --- Data Reflect Section ---
const handleFileChange = (file, fileList) => {
  publishFiles.value = fileList;
};
const removePublishFile = (index) => {
  publishFiles.value.splice(index, 1);
};

const startPublish = async () => {
  const loadingInstance = ElLoading.service({ lock: true, text: '実績反映の準備中...', background: 'rgba(0, 0, 0, 0.7)' });
  isPublishing.value = true;
  try {
    const checkRes = await fetch('/api/publish/check-duplicates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filenames: publishFiles.value.map(f => f.name) }),
    });
    const checkData = await checkRes.json();
    if (checkData.duplicates && checkData.duplicates.length > 0) {
      await ElMessageBox.confirm(
        `以下の月のデータは既に存在します。上書きしますか？<br><strong>${checkData.duplicates.join(', ')}</strong>`,
        '重複データの警告',
        { type: 'warning', dangerouslyUseHTMLString: true }
      );
    }
    loadingInstance.text.value = '実績をデータベースに反映中...';
    await executePublish();
  } catch (err) {
    if (err !== 'cancel') {
        ElNotification({ title: 'エラー', message: err.message || '処理が中断されました', type: 'error' });
    }
  } finally {
    isPublishing.value = false;
    loadingInstance.close();
  }
};

const executePublish = async () => {
    const formData = new FormData();
    publishFiles.value.forEach((file, index) => formData.append(`file_${index}`, file.raw));
    formData.append('file_count', publishFiles.value.length);

    // 1. Upload
    const uploadRes = await fetch('/api/publish/upload', { method: 'POST', body: formData });
    const uploadData = await uploadRes.json();
    if (uploadData.status !== 'success') throw new Error(uploadData.message);

    // 2. Import
    const importRes = await fetch('/api/publish/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: uploadData.session_id }),
    });
    const importData = await importRes.json();
    if (importData.status !== 'success') throw new Error(importData.message);
    
    // 3. Generate Dashboard
    await fetch('/api/publish/generate-dashboard', { method: 'POST' });

    // 統計情報を含む通知
    const stats = importData.stats || {};
    const message = `実績の反映とダッシュボードの生成が完了しました。\n\n` +
      `・学校別売上データ: ${stats.school_sales_count || 0}件\n` +
      `・月別サマリーデータ: ${stats.monthly_summary_count || 0}件\n` +
      `・イベント別売上データ: ${stats.event_sales_count || 0}件`;
    
    ElMessageBox.alert(message, '実績反映完了', {
      confirmButtonText: 'OK',
      type: 'success',
      dangerouslyUseHTMLString: false
    });
    
    publishFiles.value = [];
    fetchDashboardStatus();
};


// --- Manager Settings Section ---
const fetchSalesmanAliases = async () => {
  const res = await fetch('/api/salesman-aliases');
  const data = await res.json();
  salesmanAliases.value = data.aliases || [];
};
const addSalesmanAlias = async () => {
  addingAlias.value = true;
  try {
    const res = await fetch('/api/salesman-aliases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_name: newAlias.from, to_name: newAlias.to }),
    });
    const data = await res.json();
    if (data.status !== 'success') throw new Error(data.message);
    ElNotification({ title: '成功', message: '変換ルールを追加しました。', type: 'success' });
    newAlias.from = '';
    newAlias.to = '';
    fetchSalesmanAliases();
  } catch (err) {
    ElNotification({ title: 'エラー', message: err.message, type: 'error' });
  } finally {
    addingAlias.value = false;
  }
};
const deleteSalesmanAlias = async (id) => {
    await fetch(`/api/salesman-aliases/${id}`, { method: 'DELETE' });
    fetchSalesmanAliases();
};

const fetchSchoolManagerOverrides = async () => {
    const res = await fetch('/api/school-manager-overrides');
    const data = await res.json();
    schoolManagerOverrides.value = data.overrides || [];
};

let schoolSearchTimeout;
const searchSchools = async (query) => {
  if (!query) {
    schoolOptions.value = [];
    return;
  }
  schoolSearchLoading.value = true;
  clearTimeout(schoolSearchTimeout);
  schoolSearchTimeout = setTimeout(async () => {
    const res = await fetch('/api/schools/list');
    const data = await res.json();
    schoolOptions.value = (data.schools || []).filter(s => s.school_name.toLowerCase().includes(query.toLowerCase()));
    schoolSearchLoading.value = false;
  }, 300);
};

const addSchoolManagerOverride = async () => {
  addingOverride.value = true;
  try {
      const [start_month, end_month] = newOverride.period || [];
      const body = {
          school_id: newOverride.school.id,
          manager: newOverride.manager,
          fiscal_year: newOverride.fiscalYear,
          start_month: start_month ? new Date(start_month).getMonth() + 1 : null,
          end_month: end_month ? new Date(end_month).getMonth() + 1 : null
      };
      const res = await fetch('/api/school-manager-overrides', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
      });
      const data = await res.json();
      if(data.status !== 'success') throw new Error(data.message);
      ElNotification({ title: '成功', message: '学校担当者を設定しました。', type: 'success' });
      fetchSchoolManagerOverrides();
      newOverride.school = null;
      newOverride.manager = '';
      newOverride.period = '';
  } catch (err) {
      ElNotification({ title: 'エラー', message: err.message, type: 'error' });
  } finally {
      addingOverride.value = false;
  }
};

const deleteSchoolManagerOverride = async (id) => {
    await fetch(`/api/school-manager-overrides/${id}`, { method: 'DELETE' });
    fetchSchoolManagerOverrides();
};


// --- Publish Section ---
const fetchDashboardStatus = async () => {
  const res = await fetch('/api/publish/dashboard-status');
  const data = await res.json();
  dashboardStatus.value = data.dashboard || {};
};

const previewDashboard = () => window.open('/api/publish/preview', '_blank');

const publishToInternalServer = async () => {
    const loadingInstance = ElLoading.service({ lock: true, text: 'ダッシュボードを公開中...', background: 'rgba(0, 0, 0, 0.7)' });
    isPublishingToServer.value = true;
    try {
        const res = await fetch('/api/publish/publish-dashboard', { method: 'POST' });
        const data = await res.json();
        if(data.status !== 'success') throw new Error(data.message);
        ElNotification({ title: '成功', message: '社内サーバーに公開しました。', type: 'success' });
        fetchDashboardStatus();
    } catch(err) {
        ElNotification({ title: 'エラー', message: err.message, type: 'error' });
    } finally {
        isPublishingToServer.value = false;
        loadingInstance.close();
    }
};

const copyPublishUrl = () => {
    navigator.clipboard.writeText(dashboardStatus.value.publishUrl);
    ElNotification({ title: 'コピーしました', type: 'success' });
};


// --- Lifecycle ---
onMounted(async () => {
  await Promise.all([
    fetchSalesmanAliases(),
    fetchSchoolManagerOverrides(),
    fetchDashboardStatus(),
    (async () => {
        const res = await fetch('/api/managers/list');
        const data = await res.json();
        availableManagers.value = data.managers || [];
    })()
  ]);
});
</script>

<style scoped>
.page-container {
  padding: 20px;
}
.box-card {
  margin-bottom: 20px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.card-header span {
  font-size: 1.2rem;
  font-weight: bold;
}
.step-label {
    font-size: 1.1rem;
    font-weight: bold;
    display: flex;
    align-items: center;
}
.upload-area {
  width: 100%;
}
.tab-description {
  font-size: 0.9rem;
  color: var(--el-text-color-secondary);
  margin-bottom: 1.5rem;
}
.action-buttons {
    display: flex;
    justify-content: center;
    gap: 1rem;
    margin-top: 1rem;
}
.publish-url-box {
    margin-top: 1.5rem;
}
</style>
