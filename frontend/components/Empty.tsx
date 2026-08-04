/** Fallback shown when the backend is unreachable or has no data yet. */
export default function Empty({ message }: { message: string }) {
  return (
    <div className="panel p-8 text-center text-sm text-muted">
      {message}
      <p className="mt-2 text-xs">
        Make sure the backend is running at{" "}
        <code className="text-cyan">NEXT_PUBLIC_API_URL</code>.
      </p>
    </div>
  );
}
