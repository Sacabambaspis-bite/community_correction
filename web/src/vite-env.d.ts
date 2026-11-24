/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_USE_MOCK?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_USER_TOKEN?: string;
  readonly VITE_ADMIN_TOKEN?: string;
  readonly VITE_SUBJECT_ID?: string;
  readonly VITE_ROLE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
