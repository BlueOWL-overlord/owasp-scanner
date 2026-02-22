import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ScanPage from './pages/ScanPage'
import ResultsPage from './pages/ResultsPage'
import IntegrationsPage from './pages/IntegrationsPage'
import Layout from './components/Layout'

function ProtectedRoute({ children }) {
  const user = localStorage.getItem('user')
  return user ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="scan" element={<ScanPage />} />
          <Route path="results/:scanId" element={<ResultsPage />} />
          <Route path="integrations" element={<IntegrationsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
