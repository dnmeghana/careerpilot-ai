export const PAGE_SIZE = 8

export function pageItems<T>(items: T[], page: number, pageSize = PAGE_SIZE) {
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize))
  return { items: items.slice((page - 1) * pageSize, page * pageSize), pageCount }
}
