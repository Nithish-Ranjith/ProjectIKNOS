import { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Clock, User } from 'lucide-react';
import { Toaster } from 'sonner';
import { ThemeToggle } from '../ThemeToggle';

const navItems = [
  { id: 'home', label: 'Dashboard', icon: <LayoutDashboard size={16} /> },
  { id: 'history', label: 'History', icon: <Clock size={16} /> },
  { id: 'profile', label: 'Profile', icon: <User size={16} /> }
];

export function AppShell() {
  const navigate = useNavigate();
  const [toasterTheme, setToasterTheme] = useState<'light' | 'dark'>(
    (localStorage.getItem('iknos_theme') ?? 'light') as 'light' | 'dark'
  );

  useEffect(() => {
    const observer = new MutationObserver(() => {
      const t = document.documentElement.getAttribute('data-theme');
      setToasterTheme((t === 'dark' ? 'dark' : 'light') as 'light' | 'dark');
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  return (
    <div className="app-layout">
      <Toaster theme={toasterTheme} position="top-center" />
      {/* GLOBAL SIDE NAV */}
      <nav className="app-sidebar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '32px', paddingLeft: '8px' }}>
          <div style={{ width: 24, height: 24, background: 'var(--color-brand)', clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)' }} />
          <div>
            <div style={{ fontSize: '15px', fontWeight: 700, lineHeight: 1 }}>IKNOS</div>
            <div style={{ fontSize: '9px', color: 'var(--color-text-secondary)', textTransform: 'uppercase' }}>Land Truth. Clearer.</div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {navItems.map(item => (
            <NavLink
              key={item.id}
              to={`/surveyor/${item.id}`}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              style={({ isActive }) => ({
                display: 'flex', alignItems: 'center', gap: '12px',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                textDecoration: 'none',
                color: isActive ? 'var(--color-brand)' : 'var(--color-text-primary)',
                background: isActive ? 'var(--color-brand-light)' : 'transparent',
                fontWeight: isActive ? 600 : 500,
                fontSize: '13px'
              })}
            >
              {({ isActive }) => (
                <>
                  <span style={{ display: 'flex', alignItems: 'center', opacity: isActive ? 1 : 0.6 }}>{item.icon}</span>
                  {item.label}
                </>
              )}
            </NavLink>
          ))}
        </div>
        
         <div style={{ marginTop: 'auto', padding: '8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
           <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
             <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--color-border)', color: 'var(--color-text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', fontWeight: 600 }}>
               DEMO
             </div>
             <ThemeToggle />
           </div>
           <button 
             onClick={() => {
               localStorage.removeItem('demo_session');
               navigate('/login');
             }}
             style={{ 
               background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-2)',
               padding: '4px 10px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer', width: '100%'
             }}
           >
             Log Out
           </button>
         </div>
      </nav>

      {/* MAIN CONTENT AREA */}
      <main className="app-main">
        <Outlet />
      </main>
      
    </div>
  );
}
