<template>
  <div class="notfound">
    <span class="code num" aria-hidden="true">404</span>
    <h1 class="title">页面不存在或已被移动</h1>
    <p class="desc">链接可能已失效，返回项目列表继续操作。</p>
    <el-button type="primary" @click="$router.push('/projects')">返回项目列表</el-button>
  </div>
</template>

<style scoped lang="less">
.notfound {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 0 @page-pad;
  text-align: center;
  animation: rise-in @dur-slow @ease-out both;
}

.code {
  font-size: 88px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.04em;
  background: linear-gradient(160deg, @c-primary 10%, @c-accent 90%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;

  @media (max-width: @bp-sm) {
    font-size: 64px;
  }
}

.title {
  margin: 20px 0 0;
  font-size: @fs-h2;
  font-weight: 700;
  color: @c-text;
}

.desc {
  margin: 8px 0 24px;
  font-size: @fs-sm;
  color: @c-text-sub;
}
</style>
