import { Link, Outlet, useLocation } from 'react-router-dom'

const navigation = [
  { name: 'Dashboard', href: '/' },
  { name: 'Chat', href: '/chat' },
  { name: 'Articles', href: '/articles' },
  { name: 'Summaries', href: '/summaries' },
  { name: 'Releases', href: '/releases' },
  { name: 'Leaderboards', href: '/leaderboards' },
  { name: 'Briefings', href: '/briefings' },
  { name: 'Sources', href: '/sources' },
  { name: 'Whitelist', href: '/whitelist' },
  { name: 'Jobs', href: '/jobs' },
]

export default function Layout() {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow">
        <div className="mx-auto max-w-7xl px-4">
          <div className="flex h-16 justify-between">
            <div className="flex">
              <div className="flex flex-shrink-0 items-center">
                <span className="text-xl font-bold text-gray-900">AI Daily</span>
              </div>
              <div className="ml-10 flex space-x-8">
                {navigation.map((item) => (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={`inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium ${
                      location.pathname === item.href
                        ? 'border-indigo-500 text-gray-900'
                        : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                    }`}
                  >
                    {item.name}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </nav>
      <main className="py-10">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
