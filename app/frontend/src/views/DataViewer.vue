<template>
  <div class="page-container">
    <header class="page-header">
      <h1>データ確認</h1>
      <p>データベースに保存されている各種集計データを確認・検索します</p>
    </header>

    <div v-if="error" class="error-message">
      {{ error }}
    </div>

    <!-- テーブル選択 -->
    <div class="card">
      <h2 class="card-title">
        <span class="step">1</span>
        テーブル選択
      </h2>
      <div class="table-select-group">
        <div
          v-for="table in dataTables"
          :key="table.id"
          :class="['table-option', { active: dataSelectedTable === table.id }]"
          @click="selectDataTable(table.id)"
        >
          <span class="table-name">{{ table.name }}</span>
          <span class="table-desc">{{ table.description }}</span>
        </div>
      </div>
    </div>

    <!-- 検索フィルター -->
    <div class="card">
      <h2 class="card-title">
        <span class="step">2</span>
        検索条件
      </h2>

      <div class="filter-grid">
        <div class="filter-item">
          <label>年度</label>
          <select v-model="dataFilters.fiscal_year">
            <option :value="null">すべて</option>
            <option v-for="year in dataFilterOptions.fiscal_years" :key="year" :value="year">
              {{ year }}年度
            </option>
          </select>
        </div>

        <div class="filter-item" v-if="dataSelectedTable !== 'member_rates'">
          <label>月</label>
          <select v-model="dataFilters.month">
            <option :value="null">すべて</option>
            <option v-for="month in 12" :key="month" :value="month">
              {{ month }}月
            </option>
          </select>
        </div>

        <div class="filter-item" v-if="dataSelectedTable !== 'monthly_summary'">
          <label>事業所</label>
          <select v-model="dataFilters.region">
            <option :value="null">すべて</option>
            <option v-for="region in dataFilterOptions.regions" :key="region" :value="region">
              {{ region }}
            </option>
          </select>
        </div>

        <div class="filter-item" v-if="dataSelectedTable !== 'monthly_summary'">
          <label>担当者</label>
          <select v-model="dataFilters.manager">
            <option :value="null">すべて</option>
            <option v-for="manager in dataFilterOptions.managers" :key="manager" :value="manager">
              {{ manager }}
            </option>
          </select>
        </div>

        <div class="filter-item" v-if="dataSelectedTable !== 'monthly_summary'">
          <label>学校名（部分一致）</label>
          <input
            type="text"
            v-model="dataFilters.school_name"
            placeholder="例: 幼稚園"
          >
        </div>

        <div class="filter-item" v-if="dataSelectedTable === 'event_sales'">
          <label>イベント開始日</label>
          <input
            type="date"
            v-model="dataFilters.event_start_date"
          >
        </div>
      </div>

      <div class="filter-actions">
        <button class="btn-secondary" @click="clearDataFilters">
          条件をクリア
        </button>
        <button class="btn-primary" @click="searchData(1)">
          🔍 検索
        </button>
      </div>
    </div>

    <!-- 検索結果 -->
    <div class="card" v-if="dataSearchResult">
      <h2 class="card-title">
        <span class="step">3</span>
        検索結果
        <span class="result-count">（{{ dataSearchResult.total_count }}件）</span>
      </h2>

      <div v-if="dataSearchResult.data.length === 0" class="no-data">
        該当するデータがありません
      </div>

      <div v-else class="data-table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th v-for="col in dataSearchResult.columns" :key="col">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in dataSearchResult.data" :key="index">
              <td v-for="col in dataSearchResult.columns" :key="col">
                {{ formatCellValue(row[col], col) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ページング -->
      <div v-if="dataSearchResult.total_count > dataPageSize" class="pagination">
        <button
          class="page-btn"
          :disabled="dataCurrentPage <= 1"
          @click="goToPage(dataCurrentPage - 1)"
        >
          前へ
        </button>
        <span class="page-info">
          {{ dataCurrentPage }} / {{ dataTotalPages }} ページ
        </span>
        <button
          class="page-btn"
          :disabled="dataCurrentPage >= dataTotalPages"
          @click="goToPage(dataCurrentPage + 1)"
        >
          次へ
        </button>
      </div>

      <!-- CSVエクスポート -->
      <div class="export-section">
        <button class="btn-success" @click="exportDataCsv">
          📥 CSVダウンロード
        </button>
        <span class="export-hint">※現在の検索条件で全件をCSV出力します</span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DataViewer',
  data() {
    return {
      error: null,
      dataTables: [
        { id: 'monthly_summary', name: '月別サマリー', description: '月ごとの売上概要' },
        { id: 'school_sales', name: '学校別売上', description: '学校ごとの月別売上' },
        { id: 'event_sales', name: 'イベント別売上', description: 'イベントごとの月別売上' },
        { id: 'member_rates', name: '会員率', description: '学校・学年ごとの会員率' },
      ],
      dataSelectedTable: 'monthly_summary',
      dataFilters: {
        fiscal_year: null,
        month: null,
        region: null,
        manager: null,
        school_name: '',
        event_start_date: '',
      },
      dataFilterOptions: {
        fiscal_years: [],
        regions: [],
        managers: [],
        schools: [],
      },
      dataSearchResult: null,
      dataCurrentPage: 1,
      dataPageSize: 50,
    };
  },
  computed: {
    dataTotalPages() {
      if (!this.dataSearchResult) return 1;
      return Math.ceil(this.dataSearchResult.total_count / this.dataPageSize);
    },
  },
  methods: {
    formatCurrency(value) {
      if (!value && value !== 0) return '-';
      return '¥' + Math.round(value).toLocaleString();
    },
    async fetchFilterOptions() {
      try {
        const response = await fetch('/api/data/filter-options');
        const data = await response.json();
        if (data.status === 'success') {
          this.dataFilterOptions = data.filters;
        }
      } catch (err) {
        this.error = 'フィルター情報の取得に失敗しました';
        console.error('フィルターオプション取得エラー:', err);
      }
    },
    selectDataTable(tableId) {
      this.dataSelectedTable = tableId;
      this.dataSearchResult = null;
      this.clearDataFilters();
    },
    clearDataFilters() {
      this.dataFilters = {
        fiscal_year: null,
        month: null,
        region: null,
        manager: null,
        school_name: '',
        event_start_date: '',
      };
      this.dataSearchResult = null;
    },
    async searchData(page = 1) {
      this.error = null;
      this.dataCurrentPage = page;
      try {
        const offset = (page - 1) * this.dataPageSize;
        const body = {
          table: this.dataSelectedTable,
          filters: this.dataFilters,
          limit: this.dataPageSize,
          offset: offset,
        };

        const response = await fetch('/api/data/search', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
        });

        const data = await response.json();
        if (data.status !== 'success') {
          throw new Error(data.message);
        }
        this.dataSearchResult = data;
      } catch (err) {
        this.error = err.message || 'データ検索中にエラーが発生しました';
      }
    },
    goToPage(page) {
      if (page >= 1 && page <= this.dataTotalPages) {
        this.searchData(page);
      }
    },
    async exportDataCsv() {
      this.error = null;
      try {
        const body = {
          table: this.dataSelectedTable,
          filters: this.dataFilters,
        };

        const response = await fetch('/api/data/export', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
        });

        if (!response.ok) {
          throw new Error('CSVエクスポートに失敗しました');
        }
        const blob = await response.blob();
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `export_${this.dataSelectedTable}.csv`;
        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
          if (filenameMatch && filenameMatch.length > 1) {
            filename = filenameMatch[1];
          }
        }
        const link = document.createElement('a');
        link.href = window.URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        window.URL.revokeObjectURL(link.href);
      } catch (err) {
        this.error = err.message || 'CSVエクスポート中にエラーが発生しました';
      }
    },
    formatCellValue(value, col) {
      if (value === null || value === undefined) return '-';
      if (col.includes('date') && typeof value === 'string' && value.match(/^\d{4}-\d{2}-\d{2}/)) {
        return value.split('T')[0];
      }
      if (col.includes('sales') || col.includes('price') || col.includes('amount') || col.includes('売上')) {
        return this.formatCurrency(value);
      }
      return value;
    },
  },
  async mounted() {
    await this.fetchFilterOptions();
  },
};
</script>

<style scoped>
/* Styles specific to DataViewer */
.table-select-group {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}
.table-option {
  padding: 1rem;
  border: 1px solid #ddd;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.table-option:hover {
  border-color: #1abc9c;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.table-option.active {
  border-color: #1abc9c;
  background-color: #f0f9f7;
  border-width: 2px;
}
.table-name {
  font-weight: bold;
  display: block;
  margin-bottom: 0.25rem;
}
.table-desc {
  font-size: 0.9rem;
  color: #666;
}
.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}
.filter-item {
  display: flex;
  flex-direction: column;
}
.filter-item label {
  margin-bottom: 0.25rem;
  font-size: 0.9rem;
}
.filter-item input, .filter-item select {
  width: 100%;
  box-sizing: border-box;
}
.filter-actions {
  margin-top: 1.5rem;
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}
.btn-secondary {
    background-color: #95a5a6;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 4px;
    cursor: pointer;
}
.result-count {
  font-size: 1rem;
  font-weight: normal;
  color: #777;
  margin-left: 0.5rem;
}
.no-data {
  text-align: center;
  padding: 2rem;
  color: #777;
}
.data-table-wrapper {
  overflow-x: auto;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
}
.data-table th, .data-table td {
  border: 1px solid #ddd;
  padding: 0.75rem;
  text-align: left;
  white-space: nowrap;
}
.data-table th {
  background-color: #f7f9fa;
  font-weight: bold;
}
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: 1.5rem;
}
.page-btn {
  padding: 0.5rem 1rem;
  margin: 0 0.5rem;
  border: 1px solid #ccc;
  background: white;
  cursor: pointer;
}
.page-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
.export-section {
  margin-top: 1.5rem;
  text-align: right;
}
.btn-success {
  background-color: #27ae60;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
}
.export-hint {
  font-size: 0.85rem;
  color: #777;
  margin-left: 1rem;
}
</style>