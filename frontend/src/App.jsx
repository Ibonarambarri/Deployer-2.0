import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard';
import LogsPage from './pages/LogsPage';
import ToastContainer from './components/common/ToastContainer';

function App() {
  return (
    <Router>
      <div className="App">
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/logs/:projectName" element={<LogsPage />} />
          </Routes>
        </Layout>
        <ToastContainer />
      </div>
    </Router>
  );
}

export default App;