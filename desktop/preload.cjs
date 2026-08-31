const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("ovcDesktop", {
  isDesktop: true,
  platform: process.platform,
});
