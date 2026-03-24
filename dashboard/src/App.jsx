import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useCallback, useState } from 'react';
import Sidebar from './components/Sidebar';
import Overview from './pages/Overview';
import AlertQueue from './pages/AlertQueue';
import AlertInvestigation from './pages/AlertInvestigation';
import ModelEvaluation from './pages/ModelEvaluation';
import useBreakpoint from './hooks/useBreakpoint';
import './index.css';

export default function App() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { isMobile } = useBreakpoint();
  const handleCloseMobileNav = useCallback(() => setMobileNavOpen(false), []);

  return (
    <BrowserRouter>
      <Sidebar mobileOpen={mobileNavOpen} onClose={handleCloseMobileNav} />
      <main
        className="app-main flex-1 min-h-screen overflow-y-auto"
      >
        {isMobile && (
          <button
            type="button"
            className="mobile-menu-btn"
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open navigation menu"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
            Menu
          </button>
        )}
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/alerts" element={<AlertQueue />} />
          <Route path="/alerts/:id" element={<AlertInvestigation />} />
          <Route path="/evaluation" element={<ModelEvaluation />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
