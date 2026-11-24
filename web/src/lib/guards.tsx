/* 路由守卫：用户端未同意强制回 /consent；管理端非 staff 显示 403 提示。
 * 原型不做真实登录页，token / 角色由 web/.env 注入（ui@1.2 §2）。
 */
import { useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { ErrorBanner, Forbidden, LoadingState } from "../components/common/StateViews";
import { getConsent } from "../api/user";
import { errorText } from "./errorMessages";
import { ApiError } from "./http";
import { ROLE } from "./env";

type ConsentGuardState = "loading" | "granted" | "denied" | "error";

export function RequireConsent({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ConsentGuardState>("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let alive = true;
    getConsent()
      .then((envelope) => {
        if (!alive) {
          return;
        }
        if (envelope.code !== 0 || envelope.data === null) {
          setState("error");
          setMessage(errorText(envelope.code, envelope.message));
          return;
        }
        setState(envelope.data.general.granted ? "granted" : "denied");
      })
      .catch((error: unknown) => {
        if (!alive) {
          return;
        }
        setState("error");
        setMessage(
          error instanceof ApiError
            ? errorText(error.code, error.message)
            : "加载失败，请稍后重试",
        );
      });
    return () => {
      alive = false;
    };
  }, []);

  if (state === "loading") {
    return <LoadingState text="正在确认同意状态…" />;
  }
  if (state === "denied") {
    return <Navigate to="/consent" replace />;
  }
  if (state === "error") {
    return <ErrorBanner message={message} onRetry={() => window.location.reload()} />;
  }
  return <>{children}</>;
}

export function RequireStaff({ children }: { children: ReactNode }) {
  if (ROLE !== "staff") {
    return <Forbidden text="当前身份不是工作人员（staff），无法访问管理端" />;
  }
  return <>{children}</>;
}
