import { useMemo, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import starsData from '../assets/stars.json'
import './StarField.css'

const RAD = Math.PI / 180

function gnomonic(ra, dec, ra0, dec0) {
  const φ = dec * RAD
  const φ0 = dec0 * RAD
  const Δλ = (ra - ra0) * RAD
  const cos_c =
    Math.sin(φ0) * Math.sin(φ) + Math.cos(φ0) * Math.cos(φ) * Math.cos(Δλ)
  if (cos_c < 0.1) return null
  return {
    x: (Math.cos(φ) * Math.sin(Δλ)) / cos_c,
    y: (Math.cos(φ0) * Math.sin(φ) - Math.sin(φ0) * Math.cos(φ) * Math.cos(Δλ)) / cos_c,
  }
}

function starRadius(mag) {
  return Math.max(0.5, 2.9 - mag * 0.38)
}

function starOpacity(mag) {
  return Math.max(0.36, Math.min(0.60, 0.64 - mag * 0.04))
}

export default function StarField({ cometRa, cometDec }) {
  const [size, setSize] = useState({
    w: window.innerWidth,
    h: window.innerHeight,
  })

  useEffect(() => {
    const onResize = () =>
      setSize({ w: window.innerWidth, h: window.innerHeight })
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const { cx, cy, scale } = useMemo(() => {
    const cx = size.w / 2
    // Place comet in upper-center area (not dead-center of viewport)
    const cy = size.h * 0.38
    // FOV: ~55° horizontal. tan(27.5°) ≈ 0.5206
    const scale = size.w / 2 / 0.5206
    return { cx, cy, scale }
  }, [size])

  const { projected, labels } = useMemo(() => {
    const all = starsData
      .map((star) => {
        const p = gnomonic(star.ra, star.dec, cometRa, cometDec)
        if (!p) return null
        const sx = cx + p.x * scale
        const sy = cy - p.y * scale
        if (sx < -20 || sx > size.w + 20 || sy < -20 || sy > size.h + 20)
          return null
        return {
          x: sx,
          y: sy,
          r: starRadius(star.mag),
          opacity: starOpacity(star.mag),
          mag: star.mag,
          name: star.name ?? null,
        }
      })
      .filter(Boolean)

    // top 3 brightest on-screen named stars
    const labels = all
      .filter((s) => s.name)
      .sort((a, b) => a.mag - b.mag)
      .slice(0, 3)

    return { projected: all, labels }
  }, [cometRa, cometDec, cx, cy, scale, size])

  const gradId = 'sf-atm'

  const svgEl = (
    <svg
      className="starfield"
      width={size.w}
      height={size.h}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        {/* atmospheric glow at top */}
        <radialGradient id={gradId} cx="50%" cy="0%" r="65%" fx="50%" fy="0%">
          <stop offset="0%" stopColor="#5b8dd9" stopOpacity="0.07" />
          <stop offset="100%" stopColor="#5b8dd9" stopOpacity="0" />
        </radialGradient>
        {/* soft blur — gives stars a slight halo instead of hard dots */}
        <filter id="sf-blur" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="0.75" />
        </filter>
      </defs>

      {/* atmospheric gradient */}
      <rect
        x="0"
        y="0"
        width={size.w}
        height={size.h * 0.65}
        fill={`url(#${gradId})`}
      />

      {/* stars — blurred for soft halo */}
      <g filter="url(#sf-blur)">
        {projected.map((s, i) => (
          <circle
            key={i}
            cx={s.x}
            cy={s.y}
            r={s.r}
            fill="white"
            fillOpacity={s.opacity}
          />
        ))}
      </g>

      {/* star name labels — top 3 brightest on screen */}
      {labels.map((s) => (
        <text
          key={s.name}
          x={s.x + s.r + 5}
          y={s.y - s.r - 3}
          fill="rgba(255,255,255,0.28)"
          fontSize="9.5"
          fontFamily="'Geist Mono', monospace"
          letterSpacing="0.06em"
        >
          {s.name}
        </text>
      ))}

      {/* comet reticle — marks C/2025 R3 position */}
      <g
        className="starfield__reticle"
        transform={`translate(${cx},${cy})`}
        opacity="0.55"
      >
        <line x1="-10" y1="0" x2="-4" y2="0" stroke="#5b8dd9" strokeWidth="0.6" />
        <line x1="4" y1="0" x2="10" y2="0" stroke="#5b8dd9" strokeWidth="0.6" />
        <line x1="0" y1="-10" x2="0" y2="-4" stroke="#5b8dd9" strokeWidth="0.6" />
        <line x1="0" y1="4" x2="0" y2="10" stroke="#5b8dd9" strokeWidth="0.6" />
        <circle cx="0" cy="0" r="2.5" fill="none" stroke="#5b8dd9" strokeWidth="0.6" />
      </g>

      {/* today's sky caption */}
      <text
        className="starfield__caption"
        x={size.w - 45}
        y={size.h - 42}
        textAnchor="end"
        fill="rgba(255,255,255,0.32)"
        fontSize="13.5"
        fontFamily="'Geist Mono', monospace"
        letterSpacing="0.07em"
      >
        天区 · C/2025 R3 · 今晚
      </text>
    </svg>
  )

  return createPortal(svgEl, document.body)
}
