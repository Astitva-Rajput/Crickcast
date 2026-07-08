// same bars as the header logo, just borrowed as a loading spinner
export default function LoadingMark() {
  return (
    <svg className="brand-mark loading-mark" width="30" height="24" viewBox="0 0 20 16">
      <rect className="bar" x="0" y="6" width="4" height="10" rx="1" fill="var(--signal)" />
      <rect className="bar" x="8" y="2" width="4" height="14" rx="1" fill="var(--signal)" />
      <rect className="bar" x="16" y="9" width="4" height="7" rx="1" fill="var(--signal)" />
    </svg>
  );
}
