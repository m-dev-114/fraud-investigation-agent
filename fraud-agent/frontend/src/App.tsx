import { Routes, Route } from 'react-router-dom';
import Layout from '@/components/Layout';
import Dashboard from '@/pages/Dashboard';
import Transactions from '@/pages/Transactions';
import Investigation from '@/pages/Investigation';
import FraudNetwork from '@/pages/FraudNetwork';
import Audit from '@/pages/Audit';
import ModelPage from '@/pages/Model';
import Demo from '@/pages/Demo';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/transactions" element={<Transactions />} />
        <Route path="/investigation/:transactionId" element={<Investigation />} />
        <Route path="/network/:transactionId?" element={<FraudNetwork />} />
        <Route path="/audit/:caseId?" element={<Audit />} />
        <Route path="/model" element={<ModelPage />} />
        <Route path="/demo" element={<Demo />} />
      </Route>
    </Routes>
  );
}
