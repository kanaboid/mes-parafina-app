import { NavLink, Link, Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Operations from './pages/Operations'
import Equipment from './pages/Equipment'
import Monitoring from './pages/Monitoring'
import Filters from './pages/Filters'
import Topology from './pages/Topology'
import Pathfinder from './pages/Pathfinder'
import Parties from './pages/Parties'
import Batches from './pages/Batches'
import Apollo from './pages/Apollo'
import ApiExplorer from './pages/ApiExplorer'

function App() {
  return (
    <div className="min-h-screen bg-slate-900 text-gray-100">
      <header className="bg-slate-800 border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link to="/" className="font-extrabold text-xl">MES Parafina</Link>
          <nav className="flex flex-wrap gap-3 text-sm">
            <NavLink to="/operations" className={({isActive}) => `px-2 py-1 rounded ${isActive ? 'bg-cyan-700' : 'hover:bg-slate-700'}`}>Operacje</NavLink>
            <NavLink to="/parties" className={({isActive}) => `px-2 py-1 rounded ${isActive ? 'bg-cyan-700' : 'hover:bg-slate-700'}`}>Partie/Cykle</NavLink>
            <NavLink to="/equipment" className={({isActive}) => `px-2 py-1 rounded ${isActive ? 'bg-cyan-700' : 'hover:bg-slate-700'}`}>Sprzęt/Zawory</NavLink>
            <NavLink to="/monitoring" className={({isActive}) => `px-2 py-1 rounded ${isActive ? 'bg-cyan-700' : 'hover:bg-slate-700'}`}>Monitoring</NavLink>
            <NavLink to="/filters" className={({isActive}) => `px-2 py-1 rounded ${isActive ? 'bg-cyan-700' : 'hover:bg-slate-700'}`}>Filtry</NavLink>
            <NavLink to="/topology" className={({isActive}) => `px-2 py-1 rounded ${isActive ? 'bg-cyan-700' : 'hover:bg-slate-700'}`}>Topologia</NavLink>
            <NavLink to="/pathfinder" className={({isActive}) => `px-2 py-1 rounded ${isActive ? 'bg-cyan-700' : 'hover:bg-slate-700'}`}>Pathfinder</NavLink>
            <NavLink to="/batches" className={({isActive}) => `px-2 py-1 rounded ${isActive ? 'bg-cyan-700' : 'hover:bg-slate-700'}`}>Batches</NavLink>
            <NavLink to="/apollo" className={({isActive}) => `px-2 py-1 rounded ${isActive ? 'bg-cyan-700' : 'hover:bg-slate-700'}`}>Apollo</NavLink>
            <NavLink to="/api" className={({isActive}) => `px-2 py-1 rounded ${isActive ? 'bg-cyan-700' : 'hover:bg-slate-700'}`}>API</NavLink>
          </nav>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/operations" element={<Operations />} />
          <Route path="/equipment" element={<Equipment />} />
          <Route path="/monitoring" element={<Monitoring />} />
          <Route path="/filters" element={<Filters />} />
          <Route path="/topology" element={<Topology />} />
          <Route path="/pathfinder" element={<Pathfinder />} />
          <Route path="/parties" element={<Parties />} />
          <Route path="/batches" element={<Batches />} />
          <Route path="/apollo" element={<Apollo />} />
          <Route path="/api" element={<ApiExplorer />} />
        </Routes>
      </main>
    </div>
  )
}

export default App