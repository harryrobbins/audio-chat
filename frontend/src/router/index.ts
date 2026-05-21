import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import ProjectDetail from '../views/ProjectDetail.vue'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/project/:id', component: ProjectDetail, props: true },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
