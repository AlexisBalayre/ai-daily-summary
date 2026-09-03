import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Articles from './pages/Articles'
import Sources from './pages/Sources'
import Jobs from './pages/Jobs'
import Whitelist from './pages/Whitelist'
import Summaries from './pages/Summaries'
import Releases from './pages/Releases'
import Leaderboards from './pages/Leaderboards'
import Briefings from './pages/Briefings'
import Chat from './pages/Chat'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="articles" element={<Articles />} />
          <Route path="sources" element={<Sources />} />
          <Route path="summaries" element={<Summaries />} />
          <Route path="releases" element={<Releases />} />
          <Route path="leaderboards" element={<Leaderboards />} />
          <Route path="briefings" element={<Briefings />} />
          <Route path="chat" element={<Chat />} />
          <Route path="whitelist" element={<Whitelist />} />
          <Route path="jobs" element={<Jobs />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
