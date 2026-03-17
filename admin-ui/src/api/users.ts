import api from './client'
import { UserRead } from './auth'

export interface UserUpdateAdmin {
  is_approved?: boolean
  is_active?: boolean
  is_superadmin?: boolean
  display_name?: string
  email?: string
}

export const fetchUsers = () => api.get<UserRead[]>('/admin/users')
export const updateUser = (id: string, data: UserUpdateAdmin) => api.put<UserRead>(`/admin/users/${id}`, data)
export const approveUser = (id: string) => api.post<UserRead>(`/admin/users/${id}/approve`)
export const rejectUser = (id: string) => api.post<UserRead>(`/admin/users/${id}/reject`)
export const deleteUser = (id: string) => api.delete(`/admin/users/${id}`)
