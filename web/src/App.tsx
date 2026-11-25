/* 路由总览：用户端登录页合并知情同意，采集拆分为模块选择、签到与汇报。
 * 管理端不再保留独立状态看板，状态概览合并进对象详情（/admin/subjects/:subjectId）。
 */
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AdminLayout from "./admin/AdminLayout";
import SubjectDetailPage from "./admin/SubjectDetail/SubjectDetailPage";
import SubjectListPage from "./admin/Subjects/SubjectListPage";
import TicketDetailPage from "./admin/Tickets/Detail/TicketDetailPage";
import TicketsPage from "./admin/Tickets/TicketsPage";
import { EntryPage, NotFoundPage } from "./EntryPages";
import { RequireStaff, RequireUser } from "./lib/guards";
import CapturePage from "./user/Capture/CapturePage";
import CaptureTasksPage from "./user/Capture/CaptureTasksPage";
import CheckinPage from "./user/Checkin/CheckinPage";
import ComingSoonPage from "./user/ComingSoon/ComingSoonPage";
import FeedbackPage from "./user/Feedback/FeedbackPage";
import LoginPage from "./user/Login/LoginPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<EntryPage />} />

        <Route path="/login" element={<LoginPage />} />
        {/* 独立同意页已合并至登录页，旧地址仅做跳转，避免书签失效。 */}
        <Route path="/consent" element={<Navigate to="/login" replace />} />

        <Route
          path="/capture"
          element={
            <RequireUser>
              <CaptureTasksPage />
            </RequireUser>
          }
        />
        <Route
          path="/capture/checkin"
          element={
            <RequireUser>
              <CheckinPage />
            </RequireUser>
          }
        />
        <Route
          path="/capture/report"
          element={
            <RequireUser>
              <CapturePage />
            </RequireUser>
          }
        />
        <Route
          path="/pending"
          element={
            <RequireUser>
              <ComingSoonPage />
            </RequireUser>
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
          {/* 独立状态看板已下线，旧地址跳转到对象列表。 */}
          <Route path="dashboard" element={<Navigate to="/admin/subjects" replace />} />
          <Route path="tickets" element={<TicketsPage />} />
          <Route path="tickets/:ticketId" element={<TicketDetailPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
