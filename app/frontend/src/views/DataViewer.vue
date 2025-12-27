<template>
  <div v-loading="isLoading" element-loading-text="処理を実行しています..." class="page-container">
    <el-header class="page-header">
      <h1 class="page-title">データ確認</h1>
      <p class="page-description">データベースに保存されている各種集計データを確認・検索します。</p>
    </el-header>

    <el-alert v-if="error" :title="error" type="error" show-icon @close="error = null" />

    <el-card class="box-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span><el-icon><DataAnalysis /></el-icon> 1. 確認するデータを選択</span>
        </div>
      </template>
      <el-radio-group v-model="selectedTable" size="large" @change="onTableChange">
        <el-radio-button
          v-for="table in dataTables"
          :key="table.id"
          :label="table.id"
          :value="table.id"
        >
          {{ table.name }}
        </el-radio-button>
      </el-radio-group>
      <p class="table-description">{{ selectedTableDescription }}</p>
    </el-card>

    <el-card class="box-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span><el-icon><Filter /></el-icon> 2. 検索条件</span>
        </div>
      </template>
      <el-form :model="filters" label-position="top">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="年度">
              <el-select v-model="filters.fiscal_year" placeholder="すべて" clearable style="width: 100%;">
                <el-option v-for="year in filterOptions.fiscal_years" :key="year" :label="`${year}年度`" :value="year" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6" v-if="selectedTable !== 'member_rates'">
            <el-form-item label="月">
              <el-select v-model="filters.month" placeholder="すべて" clearable style="width: 100%;">
                <el-option v-for="month in 12" :key="month" :label="`${month}月`" :value="month" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6" v-if="selectedTable !== 'monthly_summary'">
            <el-form-item label="事業所">
               <el-select v-model="filters.region" placeholder="すべて" clearable style="width: 100%;">
                <el-option v-for="region in filterOptions.regions" :key="region" :label="region" :value="region" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6" v-if="selectedTable !== 'monthly_summary'">
            <el-form-item label="担当者">
              <el-select v-model="filters.manager" placeholder="すべて" clearable style="width: 100%;">
                <el-option v-for="manager in filterOptions.managers" :key="manager" :label="manager" :value="manager" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12" v-if="selectedTable !== 'monthly_summary'">
            <el-form-item label="学校名（部分一致）">
              <el-input v-model="filters.school_name" placeholder="例: 幼稚園" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12" v-if="selectedTable === 'event_sales'">
            <el-form-item label="イベント開始日">
               <el-date-picker v-model="filters.event_start_date" type="date" placeholder="日付を選択" value-format="YYYY-MM-DD" style="width: 100%;"/>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <div class="form-actions">
        <el-button @click="clearFilters" :icon="Refresh">条件をクリア</el-button>
        <el-button type="primary" @click="searchData(1)" :icon="Search">検索</el-button>
      </div>
    </el-card>

    <el-card v-if="searchResult" class="box-card" shadow="never">
       <template #header>
        <div class="card-header">
          <span><el-icon><Document /></el-icon> 3. 検索結果</span>
           <span class="result-count">（{{ searchResult.total_count }}件）</span>
        </div>
      </template>

      <div v-if="searchResult.data.length === 0" class="no-data">
        <el-empty description="該当するデータがありません" />
      </div>

      <div v-else>
        <el-table :data="searchResult.data" stripe style="width: 100%">
          <el-table-column
            v-for="col in searchResult.columns"
            :key="col"
            :prop="col"
            :label="col"
            sortable
            :formatter="formatCellValue"
             min-width="150"
          />
        </el-table>

        <el-pagination
          v-if="searchResult.total_count > pageSize"
          background
          layout="prev, pager, next, jumper, ->, total"
          :total="searchResult.total_count"
          :page-size="pageSize"
          :current-page="currentPage"
          @current-change="goToPage"
          class="pagination-container"
        />
      </div>

       <div class="export-section">
        <el-button type="success" @click="exportDataCsv" :icon="Download">
          CSVダウンロード
        </el-button>
        <span class="export-hint">現在の検索条件で全件をCSV出力します</span>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  Search,
  Refresh,
  Download,
  DataAnalysis,
  Filter,
  Document
} from '@element-plus/icons-vue';

const isLoading = ref(false);
const error = ref(null);

const dataTables = ref([
  { id: 'monthly_summary', name: '月別サマリー', description: '月ごとの売上概要' },
  { id: 'school_sales', name: '学校別売上', description: '学校ごとの月別売上' },
  { id: 'event_sales', name: 'イベント別売上', description: 'イベントごとの月別売上' },
  { id: 'member_rates', name: '会員率', description: '学校・学年ごとの会員率' },
]);

const selectedTable = ref('monthly_summary');

const selectedTableDescription = computed(() => {
  const table = dataTables.value.find(t => t.id === selectedTable.value);
  return table ? table.description : '';
});


const initialFilters = () => ({
  fiscal_year: null,
  month: null,
  region: null,
  manager: null,
  school_name: '',
  event_start_date: '',
});

const filters = reactive(initialFilters());

const filterOptions = reactive({
  fiscal_years: [],
  regions: [],
  managers: [],
  schools: [],
});

const searchResult = ref(null);
const currentPage = ref(1);
const pageSize = ref(50);

const onTableChange = () => {
  searchResult.value = null;
  clearFilters();
};

const clearFilters = () => {
  Object.assign(filters, initialFilters());
  searchResult.value = null;
};

const fetchFilterOptions = async () => {
  try {
    const response = await fetch('/api/data/filter-options');
    const data = await response.json();
    if (data.status === 'success') {
      Object.assign(filterOptions, data.filters);
    }
  } catch (err) {
    error.value = 'フィルター情報の取得に失敗しました';
    console.error('フィルターオプション取得エラー:', err);
  }
};

const searchData = async (page = 1) => {
  error.value = null;
  isLoading.value = true;
  currentPage.value = page;
  try {
    const offset = (page - 1) * pageSize.value;
    const body = {
      table: selectedTable.value,
      filters: { ...filters },
      limit: pageSize.value,
      offset: offset,
    };
    const response = await fetch('/api/data/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (data.status !== 'success') throw new Error(data.message);
    searchResult.value = data;
  } catch (err) {
    error.value = err.message || 'データ検索中にエラーが発生しました';
  } finally {
    isLoading.value = false;
  }
};

const goToPage = (page) => {
  if (page >= 1) {
    searchData(page);
  }
};

const exportDataCsv = async () => {
  error.value = null;
  isLoading.value = true;
  try {
    const body = {
      table: selectedTable.value,
      filters: { ...filters },
    };
    const response = await fetch('/api/data/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error('CSVエクスポートに失敗しました');

    const blob = await response.blob();
    const contentDisposition = response.headers.get('Content-Disposition');
    let filename = `export_${selectedTable.value}.csv`;
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
      if (filenameMatch?.[1]) {
        filename = decodeURIComponent(filenameMatch[1]);
      }
    }
    const link = document.createElement('a');
    link.href = window.URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(link.href);
    ElMessage.success('CSVファイルのダウンロードを開始しました。');
  } catch (err) {
    error.value = err.message || 'CSVエクスポート中にエラーが発生しました';
    ElMessage.error(error.value);
  } finally {
    isLoading.value = false;
  }
};

const formatCurrency = (value) => {
  if (value === null || value === undefined) return '-';
  const num = Number(value);
  if (isNaN(num)) return value;
  return `¥${Math.round(num).toLocaleString()}`;
};

const formatCellValue = (row, column, cellValue) => {
  if (cellValue === null || cellValue === undefined) return '-';
  const prop = column.property;
  if (prop.includes('date') && typeof cellValue === 'string' && cellValue.match(/^\d{4}-\d{2}-\d{2}/)) {
    return cellValue.split('T')[0];
  }
   if (['sales', 'price', 'amount', 'cost', 'profit', 'total'].some(term => prop.toLowerCase().includes(term)) || prop.includes('売上') || prop.includes('金額')) {
    return formatCurrency(cellValue);
  }
  return cellValue;
};


onMounted(fetchFilterOptions);

</script>

<style scoped>
.page-container {
  padding: 20px;
}
.page-header {
  margin-bottom: 20px;
}
.page-title {
  font-size: 24px;
  font-weight: 600;
}
.page-description {
  font-size: 14px;
  color: #606266;
}
.box-card {
  margin-bottom: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}
.card-header .el-icon {
  margin-right: 8px;
  vertical-align: middle;
}
.table-description {
  margin-top: 15px;
  font-size: 14px;
  color: #909399;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
.result-count {
  font-size: 14px;
  font-weight: normal;
  color: #909399;
  margin-left: 10px;
}
.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}
.export-section {
  margin-top: 20px;
  text-align: right;
}
.export-hint {
  font-size: 13px;
  color: #909399;
  margin-left: 10px;
}
.no-data {
  text-align: center;
  padding: 40px 0;
}
</style>
