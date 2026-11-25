/* 环境配置统一从这里读取，避免页面里散落 import.meta.env。 */
export const USE_MOCK = (import.meta.env.VITE_USE_MOCK ?? "1") !== "0";
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
export const USER_TOKEN = import.meta.env.VITE_USER_TOKEN ?? "user_demo";
export const ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN ?? "admin_demo";
export const SUBJECT_ID =
  import.meta.env.VITE_SUBJECT_ID ?? "d0676c19-7042-5d41-ba03-3c855a301acd";
export const ROLE = import.meta.env.VITE_ROLE ?? "staff";

/* 开发阶段演示账号：仅用于本地联调，生产环境需替换为真实认证。 */
export const DEMO_USERNAME = import.meta.env.VITE_DEMO_USERNAME ?? "张三";
export const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD ?? "123456";
