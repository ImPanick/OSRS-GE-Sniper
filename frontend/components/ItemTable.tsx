interface Column<T> {
  key: string
  label: string
  render: (item: T) => React.ReactNode
}

interface ItemTableProps<T> {
  items: T[]
  columns: Column<T>[]
}

export function ItemTable<T extends { id: number }>({ items, columns }: ItemTableProps<T>) {
  if (items.length === 0) {
    return (
      <div className="text-center py-8 text-dark-400">
        No items available
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-dark-700">
            {columns.map((column) => (
              <th
                key={column.key}
                className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase tracking-wider"
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-dark-700">
          {items.map((item) => (
            <tr
              key={item.id}
              className="hover:bg-dark-700/50 transition-colors"
            >
              {columns.map((column) => (
                <td key={column.key} className="px-4 py-3 text-sm text-dark-200">
                  {column.render(item)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

