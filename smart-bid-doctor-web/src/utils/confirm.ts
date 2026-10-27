/**
 * 二次确认统一入口（AGENTS 规则）：删除、退出、扣费、下单等破坏性或花费类操作必须经此。
 * 上传、生成清单、主题切换等高频/可逆操作不弹确认，避免打断主流程。
 */
import { ElMessageBox } from 'element-plus'

export interface ConfirmOptions {
  title?: string
  confirmText?: string
  cancelText?: string
  /** 危险操作（删除等）：确认按钮使用红色 */
  danger?: boolean
}

export async function confirmAction(message: string, opts: ConfirmOptions = {}): Promise<boolean> {
  try {
    await ElMessageBox.confirm(message, opts.title ?? '操作确认', {
      confirmButtonText: opts.confirmText ?? '确认',
      cancelButtonText: opts.cancelText ?? '取消',
      type: opts.danger ? 'warning' : 'info',
      confirmButtonClass: opts.danger ? 'el-button--danger' : '',
      // 确认类弹窗禁止点遮罩关闭，避免误触后状态不明
      closeOnClickModal: false,
    })
    return true
  } catch {
    return false
  }
}
