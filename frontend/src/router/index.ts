import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomePage.vue'),
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('../views/KnowledgePage.vue'),
    },
    {
      path: '/upload',
      name: 'upload',
      component: () => import('../views/UploadPage.vue'),
    },
    {
      path: '/qa',
      name: 'qa',
      component: () => import('../views/QAPage.vue'),
    },
    {
      path: '/exam',
      name: 'exam',
      component: () => import('../views/ExamPage.vue'),
    },
  ],
})

export default router
