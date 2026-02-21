import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Shield, Upload, LayoutDashboard, GitBranch, LogOut, User } from 'lucide-react'

export default function Navbar() {
  const navigate = useNavigate()
  const location = useLocation()
  const user = JSON.parse(localStorage.getItem('user') || '{}')

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  const isActive = (path) => location.pathname === path

  return (
    <nav className="bg-gray-900 border-b border-gray-800 sticky top-0 z-50">
      <div className="container mx-auto px-4 max-w-7xl">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 text-white font-bold text-lg">
            <Shield className="w-6 h-6 text-blue-500" />
            <span>OWASP Scanner</span>
          </Link>

          {/* Nav links */}
          <div className="flex items-center gap-1">
            <NavLink to="/" active={isActive('/')} icon={<LayoutDashboard size={16} />}>
              Dashboard
            </NavLink>
            <NavLink to="/scan" active={isActive('/scan')} icon={<Upload size={16} />}>
              New Scan
            </NavLink>
            <NavLink to="/integrations" active={isActive('/integrations')} icon={<GitBranch size={16} />}>
              CI/CD
            </NavLink>
          </div>

          {/* User menu */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <User size={14} />
              <span>{user.username || 'User'}</span>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 text-gray-400 hover:text-red-400 transition-colors text-sm"
            >
              <LogOut size={15} />
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
  )
}

function NavLink({ to, active, icon, children }) {
  return (
    <Link
      to={to}
      className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-blue-600/20 text-blue-400'
          : 'text-gray-400 hover:text-white hover:bg-gray-800'
      }`}
    >
      {icon}
      {children}
    </Link>
  )
}
