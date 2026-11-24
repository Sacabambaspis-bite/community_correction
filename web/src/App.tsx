/* 路由总览对齐 ui@1.2 §2：用户端采集拆分为模块选择、签到与汇报。 */
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AdminLayout from "./admin/AdminLayout";
import DashboardPage from "./admin/Dashboard/DashboardPage";
import SubjectDetailPage from "./admin/SubjectDetail/SubjectDetailPage";
import SubjectListPage from "./admin/Subjects/SubjectListPage";
import TicketDetailPage from "./admin/Tickets/Detail/TicketDetailPage";
import TicketsPage from "./admin/Tickets/TicketsPage";
import { EntryPage, NotFoundPage } from "./EntryPages";
import { RequireConsent, RequireStaff } from "./lib/guards";
import CapturePage from "./user/Capture/CapturePage";
import CaptureTasksPage from "./user/Capture/CaptureTasksPage";
import CheckinPage from "./user/Checkin/CheckinPage";
import ConsentPage from "./user/Consent/ConsentPage";
import FeedbackPage from "./user/Feedback/FeedbackPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<EntryPage />} />

        <Route path="/consent" element={<ConsentPage />} />
        <Route
          path="/capture"
          element={
            <RequireConsent>
              <CaptureTasksPage />
            </RequireConsent>
          }
        />
        <Route
          path="/capture/checkin"
          element={
            <RequireConsent>
              <CheckinPage />
            </RequireConsent>
          }
        />
        <Route
          path="/capture/report"
          element={
            <RequireConsent>
              <CapturePage />
            </RequireConsent>
          }
        />
        <Route path="/feedback/:sessionId" element={<FeedbackPage />} />

        <Route
          path="/admin"
          element={
            <RequireStaff>
              <AdminLayout />
            </RequireStaff>
          }
        >
          <Route index element={<Navigate to="subjects" replace />} />
          <Route path="subjects" element={<SubjectListPage />} />
          <Route path="subjects/:subjectId" element={<SubjectDetailPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="tickets" element={<TicketsPage />} />
          <Route path="tickets/:ticketId" element={<TicketDetailPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
