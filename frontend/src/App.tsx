import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Articles from './pages/Articles'
import Sources from './pages/Sources'
import Jobs from './pages/Jobs'
import Whitelist from './pages/Whitelist'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="articles" element={<Articles />} />
          <Route path="sources" element={<Sources />} />
          <Route path="whitelist" element={<Whitelist />} />
          <Route path="jobs" element={<Jobs />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
