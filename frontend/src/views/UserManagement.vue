<template>
  <div class="user-management">
    <!-- 顶部操作栏 -->
    <div class="page-header">
      <h2>用户管理</h2>
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon>新建用户
      </el-button>
    </div>

    <!-- 用户列表 -->
    <el-card shadow="never">
      <el-table :data="users" stripe v-loading="loading" empty-text="暂无用户">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" width="150" />
        <el-table-column prop="display_name" label="显示名" width="150" />
        <el-table-column prop="email" label="邮箱" min-width="200" />
        <el-table-column prop="role" label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
              {{ row.role === 'admin' ? '管理员' : '操作部' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small" effect="plain">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_active" label="最后活跃" width="170">
          <template #default="{ row }">
            {{ row.last_active ? new Date(row.last_active).toLocaleString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="editUser(row)">编辑</el-button>
            <el-popconfirm
              v-if="row.id !== currentUserId"
              title="确认删除该用户？"
              @confirm="deleteUser(row)"
            >
              <template #reference>
                <el-button text type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建用户对话框 -->
    <el-dialog v-model="showCreate" title="新建用户" width="450px">
      <el-form :model="form" label-width="80px" :rules="rules" ref="formRef">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="登录密码" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="form.display_name" placeholder="显示名称（选填）" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="邮箱（选填）" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="form.role">
            <el-radio value="operator">操作部</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="saving">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑用户对话框 -->
    <el-dialog v-model="showEdit" title="编辑用户" width="450px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="editForm.password" type="password" show-password placeholder="留空不修改" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="editForm.display_name" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="editForm.email" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="editForm.role">
            <el-radio value="operator">操作部</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" @click="handleEdit" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import client from '../api/client'

const currentUserId = ref(0)
const users = ref([])
const loading = ref(false)
const saving = ref(false)

// 创建
const showCreate = ref(false)
const formRef = ref(null)
const form = ref({ username: '', password: '', display_name: '', email: '', role: 'operator' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

// 编辑
const showEdit = ref(false)
const editForm = ref({ id: 0, username: '', password: '', display_name: '', email: '', role: 'operator', is_active: true })

async function fetchUsers() {
  loading.value = true
  try {
    const r = await client.get('/users')
    if (r.data.success) users.value = r.data.data
  } catch {
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  saving.value = true
  try {
    await client.post('/users', form.value)
    ElMessage.success('用户创建成功')
    showCreate.value = false
    form.value = { username: '', password: '', display_name: '', email: '', role: 'operator' }
    fetchUsers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    saving.value = false
  }
}

function editUser(row) {
  editForm.value = {
    id: row.id,
    username: row.username,
    password: '',
    display_name: row.display_name,
    email: row.email,
    role: row.role,
    is_active: !!row.is_active,
  }
  showEdit.value = true
}

async function handleEdit() {
  saving.value = true
  try {
    const body = {
      display_name: editForm.value.display_name,
      email: editForm.value.email,
      role: editForm.value.role,
      is_active: editForm.value.is_active,
    }
    if (editForm.value.password) body.password = editForm.value.password

    await client.put(`/users/${editForm.value.id}`, body)
    ElMessage.success('已保存')
    showEdit.value = false
    fetchUsers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function deleteUser(row) {
  try {
    await client.delete(`/users/${row.id}`)
    ElMessage.success(`已删除 ${row.username}`)
    fetchUsers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

// 获取当前用户ID
async function fetchMe() {
  try {
    const r = await client.get('/auth/me')
    currentUserId.value = r.data.id
  } catch {}
}

onMounted(() => {
  fetchMe()
  fetchUsers()
})
</script>

<style scoped>
.user-management { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 20px; }
</style>
