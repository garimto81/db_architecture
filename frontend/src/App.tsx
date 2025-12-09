/**
 * App Component - 메인 애플리케이션 루트
 * BLOCK_FRONTEND / FrontendAgent
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/layout';
import { ErrorBoundary, ToastContainer } from './components/common';
import { Dashboard, Sync, Logs } from './pages';

// TanStack Query 클라이언트 설정
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30000,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Layout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/sync" element={<Sync />} />
              <Route path="/logs" element={<Logs />} />
            </Routes>
          </Layout>
          {/* 전역 토스트 알림 */}
          <ToastContainer />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
