import { useLocation } from 'react-router-dom';
import Header from './Header';

const Layout = ({ children }) => {
  const location = useLocation();
  const isLogsPage = location.pathname.startsWith('/logs/');

  return (
    <div className="min-h-screen bg-gray-50">
      {!isLogsPage && <Header />}
      <main className={isLogsPage ? "h-screen" : "pt-16"}>
        {children}
      </main>
    </div>
  );
};

export default Layout;