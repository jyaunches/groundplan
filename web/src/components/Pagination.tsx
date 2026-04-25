type Props = {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, pageSize, total, onPageChange }: Props) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(total, page * pageSize)

  const btn = (label: string, target: number, disabled: boolean) => (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onPageChange(target)}
      className="rounded border border-stone-300 px-3 py-1 text-sm enabled:hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {label}
    </button>
  )

  return (
    <div className="flex items-center justify-between gap-3 border-t border-stone-200 bg-white px-4 py-3 text-sm text-stone-600">
      <span>
        {total === 0 ? 'No results' : `${start}–${end} of ${total}`}
      </span>
      <div className="flex items-center gap-2">
        {btn('‹ Prev', page - 1, page <= 1)}
        <span>Page {page} of {pageCount}</span>
        {btn('Next ›', page + 1, page >= pageCount)}
      </div>
    </div>
  )
}
