import api from './client'

export interface AuthPermission {
  id: string
  slug: string
  name: string
  description: string | null
  created_at: string
}

export interface AuthRole {
  id: string
  slug: string
  name: string
  description: string | null
  is_default: boolean
  is_system: boolean
  is_admin_role: boolean
  permissions: AuthPermission[]
  created_at: string
  updated_at: string
}

// Permissions
export const fetchPermissions = (systemId: string) =>
  api.get<AuthPermission[]>(`/admin/auth-systems/${systemId}/permissions`)

export const createPermission = (systemId: string, data: { slug: string; name: string; description?: string }) =>
  api.post<AuthPermission>(`/admin/auth-systems/${systemId}/permissions`, data)

export const updatePermission = (systemId: string, id: string, data: { name?: string; description?: string }) =>
  api.put<AuthPermission>(`/admin/auth-systems/${systemId}/permissions/${id}`, data)

export const deletePermission = (systemId: string, id: string) =>
  api.delete(`/admin/auth-systems/${systemId}/permissions/${id}`)

// Roles
export const fetchRoles = (systemId: string) =>
  api.get<AuthRole[]>(`/admin/auth-systems/${systemId}/roles`)

export const createRole = (
  systemId: string,
  data: { slug: string; name: string; description?: string; is_default?: boolean; is_admin_role?: boolean; permission_ids: string[] }
) => api.post<AuthRole>(`/admin/auth-systems/${systemId}/roles`, data)

export const fetchRole = (systemId: string, roleId: string) =>
  api.get<AuthRole>(`/admin/auth-systems/${systemId}/roles/${roleId}`)

export const updateRole = (
  systemId: string,
  roleId: string,
  data: { name?: string; description?: string; is_default?: boolean; is_admin_role?: boolean }
) => api.put<AuthRole>(`/admin/auth-systems/${systemId}/roles/${roleId}`, data)

export const deleteRole = (systemId: string, roleId: string) =>
  api.delete(`/admin/auth-systems/${systemId}/roles/${roleId}`)

export const setRolePermissions = (systemId: string, roleId: string, permissionIds: string[]) =>
  api.put<AuthRole>(`/admin/auth-systems/${systemId}/roles/${roleId}/permissions`, { permission_ids: permissionIds })

// User roles
export const fetchUserRoles = (systemId: string, userId: string) =>
  api.get<AuthRole[]>(`/admin/auth-systems/${systemId}/users/${userId}/roles`)

export const setUserRoles = (systemId: string, userId: string, roleIds: string[]) =>
  api.put<AuthRole[]>(`/admin/auth-systems/${systemId}/users/${userId}/roles`, { role_ids: roleIds })

export const addUserRole = (systemId: string, userId: string, roleId: string) =>
  api.post(`/admin/auth-systems/${systemId}/users/${userId}/roles`, { role_id: roleId })

export const removeUserRole = (systemId: string, userId: string, roleId: string) =>
  api.delete(`/admin/auth-systems/${systemId}/users/${userId}/roles/${roleId}`)
