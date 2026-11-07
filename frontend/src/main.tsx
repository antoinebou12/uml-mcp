import * as React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { captureTokenFromUrl } from "./lib/api";
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "./index.css";

captureTokenFromUrl();
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
