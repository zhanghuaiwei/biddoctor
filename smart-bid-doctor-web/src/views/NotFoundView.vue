<template>
  <div class="notfound">
    <el-empty description="页面不存在或已被移动">
      <el-button type="primary" @click="$router.push('/projects')">返回项目列表</el-button>
    </el-empty>
  </div>
</template>

<style scoped lang="less">
.notfound {
  max-width: @page-max;
  margin: 0 auto;
  padding: 80px 16px;
}
</style>
