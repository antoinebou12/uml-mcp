import * as React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { captureTokenFromUrl } from "./lib/api";
import "./index.css";

captureTokenFromUrl();
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
