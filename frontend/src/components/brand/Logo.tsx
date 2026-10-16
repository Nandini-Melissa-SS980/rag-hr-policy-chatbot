/**
 * The HR360 Bot mark.
 *
 * A bot head with headphones and an antenna, sitting inside
 * the 360 orbit arrow. Drawn as inline SVG rather than
 * shipped as a PNG so it stays crisp at every size, recolours
 * with the theme, and costs no extra request.
 *
 * Two variants:
 *
 *   <Logo />        the full mark, orbit included. For the
 *                   sidebar and anywhere it stands alone.
 *   <BotGlyph />    the head only, no orbit. For the small
 *                   avatar beside each answer, where the
 *                   orbit would be illegible at 14px.
 *
 * `gradientId` exists because an SVG gradient is referenced by
 * a document-wide id. Two instances on one page with the same
 * id is a real bug - the second silently reuses the first -
 * so every instance gets its own.
 */

interface LogoProps {
  size?: number;
  className?: string;
  /** Unique per instance. Defaults are distinct per variant. */
  gradientId?: string;
  title?: string;
}

export function Logo({
  size = 28,
  className,
  gradientId = "hr360-orbit",
  title = "HR360 Bot",
}: LogoProps) {
  const head = `${gradientId}-head`;
  const body = `${gradientId}-body`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      className={className}
      role="img"
      aria-label={title}
    >
      <defs>
        <linearGradient
          id={gradientId}
          x1="4"
          y1="46"
          x2="60"
          y2="34"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#2f86f6" />
          <stop offset="1" stopColor="#a53cf0" />
        </linearGradient>

        <linearGradient
          id={body}
          x1="20"
          y1="40"
          x2="46"
          y2="56"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#3b6ef0" />
          <stop offset="1" stopColor="#7b4ef0" />
        </linearGradient>

        <linearGradient
          id={head}
          x1="18"
          y1="12"
          x2="48"
          y2="38"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#ffffff" />
          <stop offset="1" stopColor="#dfe6f5" />
        </linearGradient>
      </defs>

      {/* The 360 orbit, open on the right where the arrow
          head completes it. */}
      <path
        d="M11 40a21 21 0 0 0 19 12"
        stroke={`url(#${gradientId})`}
        strokeWidth="5"
        strokeLinecap="round"
      />
      <path
        d="M53 34a21 21 0 0 1-8 15"
        stroke={`url(#${gradientId})`}
        strokeWidth="5"
        strokeLinecap="round"
      />
      <path
        d="m52 42 7 4-9 4z"
        fill="#a53cf0"
      />

      {/* Antenna. */}
      <path
        d="M32 12v5"
        stroke="#1f2a5a"
        strokeWidth="2.6"
        strokeLinecap="round"
      />
      <circle cx="32" cy="9.5" r="3.5" fill="#5a5af0" />

      {/* Headphones. */}
      <rect
        x="12"
        y="22"
        width="8"
        height="12"
        rx="4"
        fill="#3b6ef0"
      />
      <rect
        x="44"
        y="22"
        width="8"
        height="12"
        rx="4"
        fill="#3b6ef0"
      />

      {/* Body. */}
      <path
        d="M18 52a14 14 0 0 1 28 0z"
        fill={`url(#${body})`}
      />

      {/* Head. */}
      <rect
        x="16"
        y="16"
        width="32"
        height="26"
        rx="12"
        fill={`url(#${head})`}
      />

      {/* Visor. */}
      <rect
        x="21"
        y="21"
        width="22"
        height="16"
        rx="7"
        fill="#1b2240"
      />

      {/* Happy eyes. */}
      <path
        d="M27 31a2.6 2.6 0 0 1 4.4 0M34.6 31a2.6 2.6 0 0 1 4.4 0"
        stroke="#4fe3e3"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** The head alone, for small avatars. */
export function BotGlyph({
  size = 16,
  className,
  gradientId = "hr360-glyph",
}: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden
    >
      <defs>
        <linearGradient
          id={gradientId}
          x1="6"
          y1="6"
          x2="26"
          y2="26"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#ffffff" />
          <stop offset="1" stopColor="#e2e8f7" />
        </linearGradient>
      </defs>

      <path
        d="M16 3v3"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="16" cy="2.5" r="2" fill="currentColor" />

      <rect
        x="2"
        y="12"
        width="5"
        height="9"
        rx="2.5"
        fill="currentColor"
        opacity="0.75"
      />
      <rect
        x="25"
        y="12"
        width="5"
        height="9"
        rx="2.5"
        fill="currentColor"
        opacity="0.75"
      />

      <rect
        x="6"
        y="7"
        width="20"
        height="18"
        rx="8"
        fill={`url(#${gradientId})`}
      />

      <rect
        x="9.5"
        y="11"
        width="13"
        height="10.5"
        rx="5"
        fill="#1b2240"
      />

      <path
        d="M13 16.6a1.8 1.8 0 0 1 2.8 0M17.4 16.6a1.8 1.8 0 0 1 2.8 0"
        stroke="#4fe3e3"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}
