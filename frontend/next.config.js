/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
  output: "standalone",
  // Bind to all interfaces so external traffic can reach the container.
  hostname: "0.0.0.0",
};

module.exports = nextConfig;
