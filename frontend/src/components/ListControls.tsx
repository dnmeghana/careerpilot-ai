import type { ReactNode } from 'react'

type ListControlsProps = {
  search: string
  onSearch: (value: string) => void
  placeholder: string
  filter?: ReactNode
  sort?: ReactNode
}

export function ListControls({ search, onSearch, placeholder, filter, sort }: ListControlsProps) {
  return (
    <div className="list-controls">
      <input aria-label="Search list" value={search} onChange={(event) => onSearch(event.target.value)} placeholder={placeholder} />
      {filter}
      {sort}
    </div>
  )
}

export function Pagination({ page, pageCount, onPageChange }: { page: number; pageCount: number; onPageChange: (page: number) => void }) {
  if (pageCount <= 1) return null
  return (
    <nav className="pagination" aria-label="Pagination">
      <button type="button" onClick={() => onPageChange(page - 1)} disabled={page === 1} aria-label="Previous page">Previous</button>
      <span>Page {page} of {pageCount}</span>
      <button type="button" onClick={() => onPageChange(page + 1)} disabled={page === pageCount} aria-label="Next page">Next</button>
    </nav>
  )
}
