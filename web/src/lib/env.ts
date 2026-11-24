/* 环境配置统一从这里读取，避免页面里散落 import.meta.env。 */
export const USE_MOCK = (import.meta.env.VITE_USE_MOCK ?? "1") !== "0";
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
export const USER_TOKEN = import.meta.env.VITE_USER_TOKEN ?? "user_demo";
export const ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN ?? "admin_demo";
export const SUBJECT_ID =
  import.meta.env.VITE_SUBJECT_ID ?? "3b1e7c90-2f4a-4d51-8c6b-7d9e0f1a2b3c";
export const ROLE = import.meta.env.VITE_ROLE ?? "staff";
