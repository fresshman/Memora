import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 端侧离线部署：导出纯静态文件到 web/out，由 FastAPI 单端口同源托管，
  // 最终用户机器无需安装 Node.js（开发热更新仍用 npm run dev）。
  output: "export",
  // 导出为 /qa/index.html，便于任意静态服务器按目录直接返回、刷新不 404。
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
