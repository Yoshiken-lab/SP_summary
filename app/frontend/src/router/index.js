import { createRouter, createWebHashHistory } from 'vue-router';
import MonthlyAggregation from '../views/MonthlyAggregation.vue';
import CumulativeAggregation from '../views/CumulativeAggregation.vue';
import Publish from '../views/Publish.vue';
import DataViewer from '../views/DataViewer.vue';

const routes = [
  {
    path: '/',
    redirect: '/monthly',
  },
  {
    path: '/monthly',
    name: 'MonthlyAggregation',
    component: MonthlyAggregation,
    meta: { title: '月次集計' }
  },
  {
    path: '/cumulative',
    name: 'CumulativeAggregation',
    component: CumulativeAggregation,
    meta: { title: '累積集計' }
  },
  {
    path: '/publish',
    name: 'Publish',
    component: Publish,
    meta: { title: '実績反映' }
  },
  {
    path: '/data',
    name: 'DataViewer',
    component: DataViewer,
    meta: { title: 'データ確認' }
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

export default router;
