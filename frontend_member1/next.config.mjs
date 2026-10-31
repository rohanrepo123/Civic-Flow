/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: '/api/core/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
      {
        source: '/api/geo/:path*',
        destination: 'http://localhost:8000/api/v1/geo/:path*',
      },
      {
        source: '/api/browser/:path*',
        destination: 'http://localhost:8002/internal/v1/:path*',
      },
    ]
  },
}

export default nextConfig
