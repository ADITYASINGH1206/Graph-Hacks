interface Props {
  size?: number
}

/** The Decision Archaeologist mark: a decision graph sitting on layers of history. */
export function Logo({ size = 26 }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" style={{ flex: 'none', display: 'block' }}>
      <rect width="64" height="64" rx="15" fill="#16130f" />
      <g stroke="#f4efe6" strokeWidth="2.4" strokeLinecap="round" fill="none">
        <path d="M32 17 17 28M32 17 47 28" strokeOpacity=".85" />
        <path d="M10 39q11-6 22 0t22 0" strokeOpacity=".95" />
        <path d="M10 47q11-6 22 0t22 0" strokeOpacity=".6" />
        <path d="M10 55q11-6 22 0t22 0" strokeOpacity=".32" />
      </g>
      <circle cx="17" cy="28" r="3.6" fill="#f4efe6" />
      <circle cx="47" cy="28" r="3.6" fill="#f4efe6" />
      <circle cx="32" cy="16" r="6.2" fill="#d2693a" />
    </svg>
  )
}
