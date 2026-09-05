import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center gap-3 bg-slate-100 text-center">
      <p className="text-4xl font-bold text-brand-800">404</p>
      <p className="text-slate-600">This page doesn't exist.</p>
      <Link to="/" className="text-sm font-medium text-brand-700 hover:underline">
        Back to dashboard
      </Link>
    </div>
  );
}
