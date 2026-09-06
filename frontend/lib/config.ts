export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export const EMAIL_PREVIEW_ENABLED = process.env.NEXT_PUBLIC_EMAIL_PREVIEW === "true";
