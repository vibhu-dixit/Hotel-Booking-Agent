type Props = {
  className?: string;
};

/** Outline microphone glyph (brand-neutral). */
export function MicIcon({ className }: Props) {
  return (
    <svg
      className={className}
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        stroke="currentColor"
        strokeWidth="1.65"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 14a3 3 0 003-3V7a3 3 0 10-6 0v4a3 3 0 003 3zm7-3a7 7 0 01-14 0M12 18v4M9 21h6"
      />
    </svg>
  );
}
