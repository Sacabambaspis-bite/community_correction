/* 用户端登录态：原型阶段使用前端演示账号，登录态存 localStorage。
 * 账号密码校验仅用于开发联调，不代表真实身份认证（见 ui.md v1.3 实现补记）。
 */
import { DEMO_PASSWORD, DEMO_USERNAME } from "./env";

const STORAGE_KEY = "cc.user.session";

export type UserSession = {
  username: string;
  at: string;
};

export function getUserSession(): UserSession | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<UserSession>;
    if (typeof parsed.username !== "string" || !parsed.username) {
      return null;
    }
    return {
      username: parsed.username,
      at: typeof parsed.at === "string" ? parsed.at : "",
    };
  } catch {
    return null;
  }
}

export function saveUserSession(username: string): void {
  const session: UserSession = {
    username,
    at: new Date().toISOString(),
  };
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // 存储不可用时不阻断本次登录，刷新后需重新登录。
  }
}

export function clearUserSession(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // 忽略存储异常。
  }
}

/** 演示账号校验：用户名与密码均匹配才返回 true。 */
export function verifyDemoAccount(username: string, password: string): boolean {
  return username.trim() === DEMO_USERNAME && password === DEMO_PASSWORD;
}
