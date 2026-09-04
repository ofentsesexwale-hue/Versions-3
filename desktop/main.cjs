/**
 * OVC CaseFile desktop shell.
 * Opens as its own application window (no browser chrome, no Chrome/Edge taskbar entry).
 */
const { app, BrowserWindow, Menu, Tray, nativeImage, shell } = require("electron");
const path = require("path");
const fs = require("fs");
const http = require("http");
const { spawn, spawnSync } = require("child_process");

const APP_NAME = "OVC CaseFile";
const API_PORT = process.env.OVC_API_PORT || "18721";
const UI_PORT = process.env.OVC_UI_PORT || "18722";
const UI_URL = `http://127.0.0.1:${UI_PORT}`;

app.setName(APP_NAME);
app.setAppUserModelId("za.npo.ovccasefile");
app.disableHardwareAcceleration();
app.commandLine.appendSwitch("disable-dev-shm-usage");
app.commandLine.appendSwitch("enable-software-rasterizer");
app.commandLine.appendSwitch("disable-gpu");
if (process.env.OVC_NO_SANDBOX !== "0") {
  app.commandLine.appendSwitch("no-sandbox");
}

let mainWindow = null;
let tray = null;
let apiProc = null;
let uiProc = null;
let stopping = false;

function packaged() {
  return app.isPackaged;
}

function repoRoot() {
  if (packaged()) return path.join(process.resourcesPath, "office");
  return path.resolve(__dirname, "..");
}

function iconPath() {
  const ico = path.join(__dirname, "icons", process.platform === "win32" ? "icon.ico" : "icon-256.png");
  return fs.existsSync(ico) ? ico : path.join(__dirname, "icons", "icon.png");
}

function pythonBin() {
  const root = repoRoot();
  const candidates = [
    path.join(root, "python", "python.exe"),
    path.join(root, "python", "python"),
    path.join(process.resourcesPath, "python", "python.exe"),
    path.join(root, "backend", ".venv", "Scripts", "python.exe"),
    path.join(root, "backend", ".venv", "bin", "python"),
    path.join(process.resourcesPath, "venv", "Scripts", "python.exe"),
    path.join(process.resourcesPath, "venv", "bin", "python"),
  ];
  const found = candidates.find((p) => fs.existsSync(p));
  if (found) return found;
  return process.platform === "win32" ? "python" : "python3";
}

function engineLogPath() {
  try {
    return path.join(app.getPath("userData"), "engine.log");
  } catch {
    return path.join(repoRoot(), "engine.log");
  }
}

function setSplashStatus(text) {
  if (!mainWindow || mainWindow.isDestroyed()) return Promise.resolve();
  const msg = JSON.stringify(String(text || ""));
  return mainWindow.webContents
    .executeJavaScript(`(function(){ var el = document.getElementById('status'); if (el) el.textContent = ${msg}; })()`)
    .catch(() => {});
}

function waitForHttp(url, timeoutMs = 45000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(url, (res) => {
        res.resume();
        resolve();
      });
      req.on("error", () => {
        if (Date.now() - start > timeoutMs) reject(new Error("Office file took too long to open."));
        else setTimeout(tick, 250);
      });
    };
    tick();
  });
}

function startOffice() {
  const root = repoRoot();
  const backend = path.join(root, "backend");
  const uiRoot = fs.existsSync(path.join(root, "frontend", "build", "index.html"))
    ? path.join(root, "frontend", "build")
    : path.join(process.resourcesPath, "ui");
  const preview = fs.existsSync(path.join(root, "preview_server.py"))
    ? path.join(root, "preview_server.py")
    : path.join(process.resourcesPath, "preview_server.py");
  const py = pythonBin();
  const pyHome = path.dirname(py);
  const logFile = engineLogPath();
  const log = fs.openSync(logFile, "a");
  fs.writeSync(log, `\n--- ${new Date().toISOString()} python=${py} ---\n`);
  const env = {
    ...process.env,
    USE_SQLITE: "true",
    PYTHONUNBUFFERED: "1",
    PATH: `${pyHome}${path.delimiter}${process.env.PATH || ""}`,
    OVC_API_PORT: API_PORT,
    OVC_API_HOST: "127.0.0.1",
    OVC_UI_PORT: UI_PORT,
    OVC_UI_HOST: "127.0.0.1",
    OVC_UI_ROOT: uiRoot,
  };
  if (fs.existsSync(path.join(pyHome, "Lib"))) env.PYTHONHOME = pyHome;

  spawnSync(py, ["manage.py", "migrate", "--noinput"], { cwd: backend, env, stdio: ["ignore", log, log], windowsHide: true });
  spawnSync(py, ["manage.py", "seed_data"], { cwd: backend, env, stdio: ["ignore", log, log], windowsHide: true });

  apiProc = spawn(py, ["manage.py", "runserver", `127.0.0.1:${API_PORT}`, "--noreload"], {
    cwd: backend,
    env,
    stdio: ["ignore", log, log],
    windowsHide: true,
  });
  uiProc = spawn(py, [preview], {
    cwd: root,
    env,
    stdio: ["ignore", log, log],
    windowsHide: true,
  });
  apiProc.on("exit", (code) => {
    if (!stopping && code) console.error("engine exit", code);
  });
}

function stopOffice() {
  stopping = true;
  for (const p of [apiProc, uiProc]) {
    if (!p || p.killed) continue;
    try {
      if (process.platform === "win32") spawn("taskkill", ["/pid", String(p.pid), "/f", "/t"], { windowsHide: true });
      else p.kill("SIGTERM");
    } catch {
      /* ignore */
    }
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1100,
    minHeight: 700,
    title: APP_NAME,
    icon: iconPath(),
    backgroundColor: "#f3ead8",
    autoHideMenuBar: true,
    show: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      backgroundThrottling: false,
    },
  });
  win.setMenuBarVisibility(false);
  win.webContents.on("did-finish-load", () => {
    win.webContents.executeJavaScript(`document.documentElement.classList.add('ovc-desktop')`).catch(() => {});
    win.webContents.insertCSS(`
      html.ovc-desktop body { background-attachment: scroll !important; background-image: none !important; background-color: #efe4cf !important; }
      html.ovc-desktop * { backdrop-filter: none !important; -webkit-backdrop-filter: none !important; filter: none !important; }
      .glass, .glass-strong { background: #fffdf6 !important; }
      .glass-tint { background: #efe6d4 !important; }
    `).catch(() => {});
    win.setTitle(APP_NAME);
  });
  win.loadFile(path.join(__dirname, "splash.html"));
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://127.0.0.1") || url.startsWith("http://localhost")) {
      return {
        action: "allow",
        overrideBrowserWindowOptions: {
          title: APP_NAME,
          icon: iconPath(),
          autoHideMenuBar: true,
          backgroundColor: "#f3ead8",
        },
      };
    }
    shell.openPath(url).catch(() => {});
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith("http://127.0.0.1") && !url.startsWith("http://localhost") && !url.startsWith("file:")) {
      event.preventDefault();
    }
  });
  return win;
}

async function boot() {
  const got = app.requestSingleInstanceLock();
  if (!got) {
    app.quit();
    return;
  }
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  await app.whenReady();
  Menu.setApplicationMenu(null);

  const image = nativeImage.createFromPath(iconPath());
  if (process.platform === "linux") app.dock?.hide?.();
  tray = new Tray(image.resize({ width: 24, height: 24 }));
  tray.setToolTip(APP_NAME);
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Show office file", click: () => mainWindow?.show() },
      { type: "separator" },
      { label: "Quit", click: () => app.quit() },
    ]),
  );

  mainWindow = createWindow();
  await new Promise((resolve) => {
    if (!mainWindow.webContents.isLoading()) {
      resolve();
      return;
    }
    mainWindow.webContents.once("did-finish-load", resolve);
    setTimeout(resolve, 2500);
  });
  try {
    await setSplashStatus("Starting the office engine…");
    await waitForHttp(UI_URL, 800);
  } catch {
    await setSplashStatus("Preparing the office file…");
    startOffice();
  }
  try {
    await setSplashStatus("Loading");
    await waitForHttp(UI_URL, 90000);
    await setSplashStatus("Almost ready…");
    await mainWindow.loadURL(UI_URL);
    mainWindow.setTitle(APP_NAME);
  } catch (err) {
    await mainWindow.loadURL(
      "data:text/html," +
        encodeURIComponent(
          `<body style="font-family:Segoe UI,sans-serif;background:#f3ead8;color:#3f3a32;padding:48px">
           <h1>Could not open the office file</h1>
           <p>${String(err.message || err)}</p>
           <p>Use the new OVC-CaseFile.exe from Downloads (it includes Python and the CaseFile engine).</p>
           <p style="color:#7a7368">Or double-click install-python-and-engine.bat once in the project folder.</p></body>`,
        ),
    );
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) mainWindow = createWindow();
    else mainWindow.show();
  });
}

app.on("before-quit", stopOffice);
app.on("window-all-closed", () => {
  stopOffice();
  app.quit();
});

boot();
