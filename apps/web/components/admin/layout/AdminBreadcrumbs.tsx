'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { ChevronRightIcon, HomeIcon } from '@heroicons/react/24/outline'

export function AdminBreadcrumbs() {
  const pathname = usePathname()

  if (pathname === '/admin/dashboard') {
    return null
  }

  const paths = pathname.split('/').filter(Boolean)
  const breadcrumbs = paths.map((path, index) => {
    const href = '/' + paths.slice(0, index + 1).join('/')
    const label = path.charAt(0).toUpperCase() + path.slice(1).replace(/-/g, ' ')

    return {
      href,
      label,
      isLast: index === paths.length - 1,
    }
  })

  return (
    <nav className="flex mb-4" aria-label="Breadcrumb">
      <ol className="flex items-center space-x-2">
        <li>
          <Link
            href="/admin/dashboard"
            className="text-gray-400 hover:text-gray-300"
          >
            <HomeIcon className="h-5 w-5" />
          </Link>
        </li>
        {breadcrumbs.map((crumb) => (
          <li key={crumb.href} className="flex items-center">
            <ChevronRightIcon className="h-5 w-5 text-gray-500 mx-2" />
            {crumb.isLast ? (
              <span className="text-gray-300 font-medium">{crumb.label}</span>
            ) : (
              <Link
                href={crumb.href}
                className="text-gray-400 hover:text-gray-300"
              >
                {crumb.label}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}

