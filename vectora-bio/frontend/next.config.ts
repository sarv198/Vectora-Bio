import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Keep the development badge clear of the sidebar footer (status and theme switch).
  devIndicators: { position: "bottom-right" },
};

export default nextConfig;
