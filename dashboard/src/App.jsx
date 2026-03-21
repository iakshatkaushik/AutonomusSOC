import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Overview from './pages/Overview';
import AlertQueue from './pages/AlertQueue';
import AlertInvestigation from './pages/AlertInvestigation';
import './index.css';

export default function App() {
  return (
    <BrowserRouter>
      <Sidebar />
      <main
        className="flex-1 min-h-screen overflow-y-auto"
        style={{ marginLeft: 260, padding: '32px 40px' }}
      >
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/alerts" element={<AlertQueue />} />
          <Route path="/alerts/:id" element={<AlertInvestigation />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
