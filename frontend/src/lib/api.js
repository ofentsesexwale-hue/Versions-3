import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
export const API = `${BACKEND_URL}/api`;

export const TOKEN_KEY = "ovc_token";

const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error?.response?.status === 401) {
      const path = window.location.pathname;
      if (path !== "/login") {
        localStorage.removeItem(TOKEN_KEY);
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// Fetch a protected file (with auth header) as an object URL for view-only display.
export async function fetchFileObjectUrl(url) {
  const token = localStorage.getItem(TOKEN_KEY);
  const res = await fetch(`${BACKEND_URL}${url}`, {
    headers: token ? { Authorization: `Token ${token}` } : {},
  });
  if (!res.ok) throw new Error("Failed to load file");
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export default api;
